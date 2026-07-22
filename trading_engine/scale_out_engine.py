from __future__ import annotations
import logging
import MetaTrader5 as mt5
from decimal import Decimal
from datetime import datetime, timezone
from django.utils import timezone as django_tz
from typing import Dict, Any, List

from broker_engine.mt5_client import MT5Client
from backend.apps.trading.models import TradingAccount, TradingSymbol, Order, OpenPosition
from telegram.bot import TelegramBotClient

logger = logging.getLogger("trading")


class ScaleOutEngine:
    """
    Multi-Stage Scale-Out & Partial Take Profit Engine.
    Monitors live MT5 open positions, checks Risk-to-Reward (RR) milestones,
    secures partial profits (50% lot reduction), and shifts SL to breakeven + spread.
    """
    def __init__(self, client: MT5Client, telegram_client: Optional[TelegramBotClient] = None):
        self.client = client
        self.telegram = telegram_client

    def evaluate_open_positions(self) -> None:
        """
        Scans all live open positions in MT5 terminal and applies scale-out rules.
        """
        # Ensure we are connected
        if not self.client.connect():
            return

        positions = self.client.mt5.positions_get() or ()
        if not positions:
            return

        for pos in positions:
            try:
                symbol = pos.symbol
                ticket = pos.ticket
                entry_price = Decimal(str(pos.price_open))
                current_price = Decimal(str(pos.price_current))
                sl = Decimal(str(pos.sl))
                tp = Decimal(str(pos.tp))
                volume = Decimal(str(pos.volume))
                pos_type = pos.type

                if sl <= Decimal("0"):
                    continue

                # Calculate Initial Risk (R)
                risk_dist = abs(entry_price - sl)
                if risk_dist <= Decimal("0"):
                    continue

                # Calculate Current Profit Distance
                if pos_type == self.client.mt5.ORDER_TYPE_BUY:
                    current_profit_dist = current_price - entry_price
                else:
                    current_profit_dist = entry_price - current_price

                current_rr = current_profit_dist / risk_dist

                # Get original order from database to check initial volume
                order_obj = Order.objects.filter(broker_ticket=str(ticket)).first()
                initial_volume = order_obj.requested_volume if order_obj else volume
                
                # STAGE 1: 1.5 RR Milestone & First Partial Close (50% reduction)
                if current_rr >= Decimal("1.5") and volume >= initial_volume:
                    # Let's perform a 50% partial close!
                    # Exness minimum volume step is 0.01. Let's round the volume to standard steps.
                    spec = self.client.mt5.symbol_info(symbol)
                    lot_step = Decimal(str(spec.volume_step if spec else "0.01"))
                    min_lot = Decimal(str(spec.volume_min if spec else "0.01"))
                    
                    close_volume = (volume * Decimal("0.5") / lot_step).to_integral_value(rounding="ROUND_DOWN") * lot_step
                    close_volume = max(min_lot, close_volume)

                    # Only proceed if we have enough volume left to close
                    if close_volume < volume:
                        logger.info(f"ScaleOutEngine: Position #{ticket} {symbol} hit 1.5R (current RR: {float(current_rr):.2f}). Initiating 50% Partial Close of {close_volume} lots...")
                        success = self._close_partial_position(ticket, symbol, close_volume, pos_type)
                        if success:
                            # Move Stop Loss to Breakeven + a tiny buffer to cover spread
                            point = Decimal(str(spec.point if spec else "0.00001"))
                            spread_buffer = point * Decimal(str(getattr(spec, "spread", 5) or 5))
                            
                            if pos_type == self.client.mt5.ORDER_TYPE_BUY:
                                new_sl = entry_price + spread_buffer
                            else:
                                new_sl = entry_price - spread_buffer

                            # Round to symbol digits
                            digits = int(spec.digits if spec else 5)
                            new_sl = round(new_sl, digits)

                            logger.info(f"ScaleOutEngine: Shifting SL of Position #{ticket} {symbol} to Breakeven level: {new_sl}")
                            self._modify_position_sltp(ticket, symbol, new_sl, tp)

                            # Dispatch Telegram Alert
                            if self.telegram:
                                subscribers = OpenPosition.objects.filter(broker_ticket=str(ticket)).values_list("account__user__telegramsubscriber__chat_id", flat=True)
                                if not subscribers or not any(subscribers):
                                    # Fallback to standard chat channel
                                    from backend.apps.notifications.models import TelegramSubscriber
                                    subscribers = list(TelegramSubscriber.objects.filter(is_deleted=False, signal_alerts=True).values_list("chat_id", flat=True))

                                msg = (
                                    f"⚡ <b>PARTIAL TP1 SECURED (50%) & SL TO BREAKEVEN</b> ⚡\n\n"
                                    f"Asset: {symbol}\n"
                                    f"Volume Reduced: {close_volume} Lots (Remaining: {float(volume - close_volume)} Lots)\n"
                                    f"Closed P/L Milestone: <b>+1.5R Risk-Free</b>\n"
                                    f"Entry Price: {entry_price}\n"
                                    f"New Stop Loss: {new_sl} (Breakeven Locked 🛡️)\n"
                                    f"Ticket: #{ticket}"
                                )
                                for chat_id in subscribers:
                                    if chat_id:
                                        try:
                                            self.telegram.send_message(chat_id, msg)
                                        except Exception:
                                            pass
                
                # STAGE 2: 3.0 RR Take Profit Milestone (Close remaining 50%)
                elif current_rr >= Decimal("3.0"):
                    logger.info(f"ScaleOutEngine: Position #{ticket} {symbol} hit 3.0R (current RR: {float(current_rr):.2f}). Closing remaining position...")
                    success = self._close_full_position(ticket, symbol, volume, pos_type)
                    if success and self.telegram:
                        from backend.apps.notifications.models import TelegramSubscriber
                        subscribers = list(TelegramSubscriber.objects.filter(is_deleted=False, signal_alerts=True).values_list("chat_id", flat=True))
                        msg = (
                            f"🎯 <b>FINAL TAKE PROFIT REACHED (1:3.0 RR)</b> 🎯\n\n"
                            f"Asset: {symbol}\n"
                            f"Volume Closed: {volume} Lots (Final Run)\n"
                            f"Profit Secured: <b>+3.0R Target Achieved</b> 🏆\n"
                            f"Exit Price: {current_price}\n"
                            f"Ticket: #{ticket}"
                        )
                        for chat_id in subscribers:
                            if chat_id:
                                try:
                                    self.telegram.send_message(chat_id, msg)
                                except Exception:
                                    pass

            except Exception as e:
                logger.error(f"ScaleOutEngine: Error evaluating position #{getattr(pos, 'ticket', 'unknown')}: {e}")

    def _close_partial_position(self, ticket: int, symbol: str, volume: Decimal, pos_type: int) -> bool:
        """
        Closes a partial volume of an active position.
        """
        tick = self.client.mt5.symbol_info_tick(symbol)
        if not tick:
            return False

        # Opposite order type
        close_type = self.client.mt5.ORDER_TYPE_SELL if pos_type == self.client.mt5.ORDER_TYPE_BUY else self.client.mt5.ORDER_TYPE_BUY
        price = tick.bid if pos_type == self.client.mt5.ORDER_TYPE_BUY else tick.ask

        request = {
            "action": self.client.mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": close_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "type_filling": self.client.mt5.ORDER_TIME_GTC
        }

        res = self.client.mt5.order_send(request)
        if res and res.retcode in [10008, 10009]:
            return True
        logger.error(f"ScaleOutEngine: Failed partial close for #{ticket}: {getattr(res, 'comment', 'No Response')}")
        return False

    def _close_full_position(self, ticket: int, symbol: str, volume: Decimal, pos_type: int) -> bool:
        """
        Closes the entire remaining volume of a position.
        """
        return self._close_partial_position(ticket, symbol, volume, pos_type)

    def _modify_position_sltp(self, ticket: int, symbol: str, sl: Decimal, tp: Decimal) -> bool:
        """
        Modifies Stop Loss and Take Profit of an active position in MT5.
        """
        request = {
            "action": self.client.mt5.TRADE_ACTION_SLTP,
            "symbol": symbol,
            "position": ticket,
            "sl": float(sl),
            "tp": float(tp)
        }
        res = self.client.mt5.order_send(request)
        if res and res.retcode in [10008, 10009]:
            return True
        logger.error(f"ScaleOutEngine: Failed modifying SL/TP for #{ticket}: {getattr(res, 'comment', 'No Response')}")
        return False
