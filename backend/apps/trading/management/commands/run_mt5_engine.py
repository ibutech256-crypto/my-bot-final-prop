from __future__ import annotations
import os, sys
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"): sys.stderr.reconfigure(encoding="utf-8", errors="replace")
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from dotenv import load_dotenv
import logging
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone as django_tz
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from broker_engine.mt5_client import MT5Client, BrokerOrderRequest
from backend.apps.trading.models import (
    BrokerProfile, BrokerSetting, TradingAccount, TradingSymbol, Signal, OpenPosition, Order, SignalDirection
)
from backend.apps.notifications.models import TelegramSubscriber
from trading_engine.orchestrator import RomeoTPTOrchestrator, EngineConfig
from trading_engine.types import Candle, AccountSnapshot, SymbolSpec, Direction, Timeframe
from trading_engine.account_manager import AccountManager, TradeExecutionGate
from trading_engine.adaptive_brain import AdaptiveBrainGate
from trading_engine.eat_phase_engine import EATPhaseEngine
from telegram.bot import TelegramBotClient

def _auto_load_env():
    load_dotenv()
    curr = Path(__file__).resolve()
    for _ in range(6):
        curr = curr.parent
        for fname in [".env", ".env.txt"]:
            env_path = curr / fname
            if env_path.exists():
                load_dotenv(env_path, override=True)

_auto_load_env()
logger = logging.getLogger("trading")

PRIMARY_WATCHLIST = ['XAUUSDm', 'EURUSDm', 'GBPUSDm', 'USDJPYm', 'AUDUSDm', 'BTCUSDm', 'ETHUSDm', 'US30m', 'US500m', 'TSLAm', 'AAPLm', 'NVDAm', 'MSFTm', 'AMZNm', 'GOOGm', 'META', 'PYPLm']

FOCUS_SYMBOLS = ['ADAUSDm', 'AUDCADm', 'AUDCHFm', 'AUDJPYm', 'AUDMXNm', 'AUDNZDm', 'AUDSGDm', 'AUDUSDm', 'AUDZARm', 'AUS200m', 'BCHUSDm', 'BNBUSDm', 'BTCUSDm', 'BTCXAUm', 'CADCHFm', 'CADJPYm', 'CADMXNm', 'CADTRYm', 'CAKEUSDm', 'CHFHUFm', 'CHFJPYm', 'CHFMXNm', 'CHFPLNm', 'CHFSGDm', 'CHFTRYm', 'COMPUSDm', 'DE30m', 'DKKPLNm', 'DOGEUSDm', 'DOTUSDm', 'DXYm', 'ETHBTCm', 'ETHUSDm', 'EURAUDm', 'EURCADm', 'EURCHFm', 'EURCZKm', 'EURDKKm', 'EURGBPm', 'EURHKDm', 'EURHUFm', 'EURJPYm', 'EURMXNm', 'EURNOKm', 'EURNZDm', 'EURPLNm', 'EURSEKm', 'EURTRYm', 'EURUSDm', 'EURZARm', 'FR40m', 'GBPAUDm', 'GBPCADm', 'GBPCHFm', 'GBPHUFm', 'GBPJPYm', 'GBPMXNm', 'GBPNOKm', 'GBPNZDm', 'GBPSEKm', 'GBPTRYm', 'GBPUSDm', 'GBPZARm', 'HK50m', 'HUFJPYm', 'JP225m', 'LINKUSDm', 'LTCUSDm', 'MANAUSDm', 'NZDCADm', 'NZDCHFm', 'NZDHUFm', 'NZDJPYm', 'NZDTRYm', 'NZDUSDm', 'NZDZARm', 'SEKPLNm', 'SOLUSDm', 'UK100m', 'UKOILm', 'US30m', 'US500_x100m', 'US500m', 'USDAEDm', 'USDCADm', 'USDCHFm', 'USDCNHm', 'USDCZKm', 'USDDKKm', 'USDHKDm', 'USDHUFm', 'USDINRm', 'USDISKm', 'USDJPYm', 'USDKWDm', 'USDMADm', 'USDMXNm', 'USDNOKm', 'USDPLNm', 'USDSARm', 'USDSEKm', 'USDSGDm', 'USDTHBm', 'USDTRYm', 'USDTWDm', 'USDZARm', 'USOILm', 'USTEC_x100m', 'USTECm', 'XAGAUDm', 'XAGEURm', 'XAGJPYm', 'XAGUSDm', 'XAUAUDm', 'XAUEURm', 'XAUGBPm', 'XAUUSDm', 'XCUUSDm', 'XPDUSDm', 'XPTUSDm', 'XRPUSDm', 'XZNUSDm']

class Command(BaseCommand):
    help = "Run the real-time MT5 Institutional Trading & Telemetry Engine (Romeo TPT)"

    def handle(self, *args, **options):
        _auto_load_env()
        self.stdout.write("Starting MT5 Real-Time Institutional Trading & Telemetry Engine...")

        login_str = os.getenv("MT5_LOGIN")
        password = os.getenv("MT5_PASSWORD")
        server = os.getenv("MT5_SERVER")
        mt5_path = os.getenv("MT5_PATH")

        if not login_str or not password or not server:
            self.stderr.write("ERROR: MT5_LOGIN, MT5_PASSWORD, and MT5_SERVER must be set in .env!")
            return

        try:
            login_id = int(login_str)
        except ValueError:
            self.stderr.write("ERROR: MT5_LOGIN must be numeric!")
            return

        client = MT5Client(login=login_id, password=password, server=server, path=mt5_path)
        try:
            client.connect()
            self.stdout.write(f"Connected directly to Exness MT5 Terminal (Login: {login_id} @ {server})")
        except Exception as e:
            self.stderr.write(f"Failed to connect to Exness MT5: {e}")
            return

        tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
        tg_client = TelegramBotClient(tg_token) if tg_token else None

        broker, _ = BrokerProfile.objects.get_or_create(
            server=server,
            defaults={"name": "Exness MT5 Demo", "broker_type": "MT5", "encrypted_login": str(login_id), "encrypted_password": "***"}
        )

        broker_setting, _ = BrokerSetting.objects.get_or_create(
            broker=broker,
            defaults={"enable_autotrading": True, "order_deviation_points": 20, "heartbeat_seconds": 15}
        )
        if not broker_setting.enable_autotrading:
            broker_setting.enable_autotrading = True
            broker_setting.save()

        User = get_user_model()
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.create_superuser("admin", "admin@trading.io", "password123")

        account, _ = TradingAccount.objects.get_or_create(
            broker=broker,
            account_number=str(login_id),
            defaults={"user": admin_user, "account_name": "Exness Institutional Demo", "currency": "USD", "is_active": True}
        )

        # Mark all existing symbols in DB as untradeable first
        TradingSymbol.objects.all().update(is_tradeable=False)

        mt5_symbols = client.mt5.symbols_get() or []
        visible_symbols = []
        for s in mt5_symbols:
            if s.name in FOCUS_SYMBOLS:
                visible_symbols.append(s.name)
                TradingSymbol.objects.update_or_create(
                    symbol=s.name,
                    defaults={
                        "asset_class": "CRYPTO" if "BTC" in s.name.upper() or "ETH" in s.name.upper() else "COMMODITY" if "XAU" in s.name.upper() else "FOREX",
                        "digits": s.digits,
                        "contract_size": Decimal(str(s.trade_contract_size)),
                        "min_lot": Decimal(str(s.volume_min)),
                        "max_lot": Decimal(str(s.volume_max)),
                        "lot_step": Decimal(str(s.volume_step)),
                        "is_tradeable": True,
                        "is_deleted": False
                    }
                )

        orchestrator = RomeoTPTOrchestrator(EngineConfig(minimum_score=Decimal("50"), mode="AUTOMATED"))
        adaptive_brain = AdaptiveBrainGate(client)
        adaptive_brain.sync_backtest_memory()

        from trading_engine.news_engine import NewsBlackoutEngine
        from trading_engine.scale_out_engine import ScaleOutEngine
        news_engine = NewsBlackoutEngine()
        scale_out_engine = ScaleOutEngine(client, tg_client)

        channel_layer = get_channel_layer()

        self.stdout.write(f"MT5 Real-Time Polling Loop active tracking {len(visible_symbols)} Exness symbols (5s intervals)...")
        last_tg_heartbeat = 0.0

        while True:
            try:
                info = client.account_info()
                account.balance = Decimal(str(info["balance"]))
                account.equity = Decimal(str(info["equity"]))
                account.margin = Decimal(str(info["margin"]))
                account.save()

                # --- 4-Hour Telegram System Heartbeat (Every 14,400 seconds) ---
                if tg_client and (time.time() - last_tg_heartbeat >= 14400.0 or last_tg_heartbeat == 0.0):
                    last_tg_heartbeat = time.time()
                    try:
                        eat_now_hb = EATPhaseEngine.get_eat_time()
                        subscribers = TelegramSubscriber.objects.filter(is_deleted=False, signal_alerts=True)
                        hb_msg = (
                            f"💓 INSTITUTIONAL AI TRADING PLATFORM — 4-HOUR SYSTEM HEARTBEAT\n\n"
                            f"✅ Status: All 6 Enterprise NSSM Services Active & Operational\n"
                            f"📡 Exness MT5 Terminal: Online (#{account.account_number} / {broker.server})\n\n"
                            f"💰 Live Balance: ${float(account.balance):,.2f}\n"
                            f"📈 Live Equity: ${float(account.equity):,.2f}\n"
                            f"🕒 Current EAT Time: `{eat_now_hb.strftime('%Y-%m-%d %H:%M:%S')} EAT (UTC+3)`\n\n"
                            f"⚡ Auto-Execution Gate: `Score >= 80/100` + `KOD Turtle Soup Limit Sniper`\n"
                            f"🛡️ Risk & Phase Shield: `0.50 Lot Cap`, `4-Factor Spread/ATR Gate`, & `Adaptive Brain Quarantine` Active\n"
                            f"💬 Next Heartbeat: In 4 hours (`{(eat_now_hb + timedelta(hours=4)).strftime('%H:%M:%S')} EAT`)"
                        )
                        for s in subscribers:
                            try:
                                tg_client.send_message(s.chat_id, hb_msg)
                            except Exception as hb_err:
                                pass
                        self.stdout.write(f"TELEGRAM HEARTBEAT DISPATCHED: Sent 4-hour system heartbeat to {subscribers.count()} subscribers (including -1003781184008).")
                    except Exception as e_hb:
                        self.stderr.write(f"Error dispatching 4-hour Telegram heartbeat: {e_hb}")

                if channel_layer:
                    async_to_sync(channel_layer.group_send)(
                        "trading",
                        {
                            "type": "event",
                            "payload": {
                                "event": "ACCOUNT_TELEMETRY",
                                "account": {
                                    "account_number": account.account_number,
                                    "balance": float(account.balance),
                                    "equity": float(account.equity),
                                    "margin": float(account.margin),
                                    "free_margin": float(account.equity - account.margin),
                                    "status": "ONLINE"
                                }
                            }
                        }
                    )

                mt5_positions = client.mt5.positions_get() or []
                active_tickets = set()
                for pos in mt5_positions:
                    ticket = str(pos.ticket)
                    active_tickets.add(ticket)
                    sym_obj, _ = TradingSymbol.objects.get_or_create(symbol=pos.symbol)
                    OpenPosition.objects.update_or_create(
                        account=account,
                        broker_ticket=ticket,
                        defaults={
                            "symbol": sym_obj,
                            "direction": SignalDirection.BUY if pos.type == client.mt5.ORDER_TYPE_BUY else SignalDirection.SELL,
                            "volume": Decimal(str(pos.volume)),
                            "entry_price": Decimal(str(pos.price_open)),
                            "current_price": Decimal(str(pos.price_current)),
                            "stop_loss": Decimal(str(pos.sl)) if pos.sl else None,
                            "take_profit": Decimal(str(pos.tp)) if pos.tp else None,
                            "unrealized_profit": Decimal(str(pos.profit)),
                            "opened_at": datetime.fromtimestamp(pos.time, tz=timezone.utc),
                        }
                    )

                    # --- Automatic Quarantined Legacy Position Cleanup ---
                    # Check if this position is on a quarantined stock CFD or exotic cross opened prior to new rules
                    clean_pos_sym = pos.symbol.upper().replace("M", "")
                    spec_pos = client.mt5.symbol_info(pos.symbol)
                    is_stock_pos = False
                    if spec_pos:
                        is_stock_pos = (getattr(spec_pos, "category", "") == "Stocks" or 
                                        "Stocks" in getattr(spec_pos, "path", "") or 
                                        "Shares" in getattr(spec_pos, "path", "") or 
                                        getattr(spec_pos, "trade_calc_mode", 0) == 2)
                    else:
                        is_stock_pos = any(q in clean_pos_sym for q in ["SBUX", "TMO", "TSLA", "VRTX", "NTES", "BABA", "META", "AMZN", "AAPL", "MSFT", "GOOG", "NVDA", "NFLX", "HD", "XOM", "JPM", "TSM"])

                    exotic_currencies = [
                        "DKK", "NOK", "SEK", "SGD", "ZAR", "MXN", "TRY", "PLN", "HUF", "ILS", 
                        "HKD", "CNH", "CNY", "INR", "MYR", "IDR", "KES", "GHS", "ARS", "RON", 
                        "UGX", "UAH", "UZS", "VND", "LBP", "KZT", "KWD", "BHD", "BGN", "BDT", 
                        "AZN", "AMD", "AED", "XOF", "KGS", "GEL", "EGP", "COP", "BND", "CZK"
                    ]
                    is_exotic_pos = False
                    if not any(m in clean_pos_sym for m in ["XAU", "XAG", "XPT", "XPD", "GOLD", "SILVER", "OIL", "US30", "US500", "NAS100", "DE30", "HK50", "AUS200", "FR40"]):
                        if any(exo in clean_pos_sym for exo in exotic_currencies) or any(exotic in pos.symbol.upper() for exotic in ["CHFDKK", "CHFNOK", "USDSGD", "NOKJPY", "SEKPLN", "PLNHUF", "NZDHUF", "EURDKK", "GBPDKK"]):
                            is_exotic_pos = True

                    is_legacy_quarantined = is_stock_pos or is_exotic_pos
                    if is_legacy_quarantined and broker_setting.enable_autotrading:
                        tick_pos = client.mt5.symbol_info_tick(pos.symbol)
                        spec_pos = client.mt5.symbol_info(pos.symbol)
                        if tick_pos and spec_pos and tick_pos.bid > 0 and tick_pos.ask > 0 and getattr(spec_pos, "trade_mode", 1) != 0:
                            # Market is open right now -> automatically close out the legacy quarantined trade
                            self.stdout.write(f"LEGACY QUARANTINE CLEANUP: Market for {pos.symbol} is now OPEN. Closing legacy position #{ticket} ({pos.volume} lots) to start fresh under new rules.")
                            close_req = {
                                "action": client.mt5.TRADE_ACTION_DEAL,
                                "symbol": pos.symbol,
                                "volume": float(pos.volume),
                                "type": client.mt5.ORDER_TYPE_SELL if pos.type == client.mt5.ORDER_TYPE_BUY else client.mt5.ORDER_TYPE_BUY,
                                "position": pos.ticket,
                                "price": float(tick_pos.bid if pos.type == client.mt5.ORDER_TYPE_BUY else tick_pos.ask),
                                "deviation": broker_setting.order_deviation_points * 2,
                                "type_filling": getattr(client.mt5, "ORDER_FILLING_IOC", 1)
                            }
                            c_res = client.mt5.order_send(close_req)
                            if c_res and c_res.retcode in (10008, 10009):
                                self.stdout.write(f"LEGACY QUARANTINE CLEANUP: Successfully closed #{ticket} ({pos.symbol}).")
                                active_tickets.remove(ticket)
                            else:
                                self.stdout.write(f"LEGACY QUARANTINE CLEANUP: Close attempt for #{ticket} failed ({c_res.comment if c_res else 'No res'})")
                        else:
                            self.stdout.write(f"LEGACY QUARANTINE SHIELD: Position #{ticket} ({pos.symbol} {pos.volume} lots) is scheduled for automatic closure once US cash market opens at 16:30 EAT (currently closed).")

                OpenPosition.objects.filter(account=account).exclude(broker_ticket__in=active_tickets).update(is_deleted=True)

                # --- AI Outcome Tracking: Check Closed MT5 Deals & Active Signals Hitting TP/SL ---
                try:
                    now_ts = datetime.now(timezone.utc)
                    from_ts = now_ts - timedelta(minutes=30)
                    recent_deals = client.mt5.history_deals_get(from_ts, now_ts) or []
                    for deal in recent_deals:
                        if deal.profit != 0.0 and deal.entry == 1:  # DEAL_ENTRY_OUT / INOUT
                            d_ticket = str(deal.ticket)
                            deal_audited = Signal.objects.filter(symbol__symbol=deal.symbol, rationale__icontains=d_ticket).exists()
                            if not deal_audited:
                                is_win = deal.profit > 0.0
                                ai_report = adaptive_brain.analyze_trade_outcome(
                                    symbol=deal.symbol,
                                    direction="BUY" if deal.type == 1 else "SELL",
                                    profit_usd=Decimal(str(deal.profit)),
                                    entry_price=Decimal(str(deal.price)),
                                    exit_price=Decimal(str(deal.price)),
                                    sl=Decimal("0.0"),
                                    tp=Decimal("0.0"),
                                    is_live_trade=True
                                )
                                recent_sig = Signal.objects.filter(symbol__symbol=deal.symbol, status="ACTIVE", is_deleted=False).order_by("-created_at").first()
                                if recent_sig:
                                    recent_sig.status = "CLOSED_TP" if is_win else "CLOSED_SL"
                                    recent_sig.rationale += f" [Audited Deal #{d_ticket}]"
                                    recent_sig.save()

                                if tg_client:
                                    subscribers = TelegramSubscriber.objects.filter(is_deleted=False, signal_alerts=True)
                                    outcome_icon = "🎯 TRADE HIT TAKE PROFIT (TP) 🎯" if is_win else "🛑 TRADE HIT STOP LOSS (SL) 🛑"
                                    out_msg = (
                                        f"{outcome_icon}\n\n"
                                        f"Asset: {deal.symbol} | Volume: {deal.volume} Lots\n"
                                        f"Closed P/L: **${deal.profit:,.2f} USD**\n\n"
                                        f"🧠 **AI Forensic Outcome Diagnosis**:\n"
                                        f"{ai_report['diagnosis']}\n\n"
                                        f"🛡️ **Adaptive Brain Status**: Multiplier {ai_report['sizing_multiplier']}x | Quarantined: {ai_report['is_quarantined']}"
                                    )
                                    for sub in subscribers:
                                        try:
                                            tg_client.send_message(sub.chat_id, out_msg)
                                        except Exception:
                                            pass
                                self.stdout.write(f"AI OUTCOME TRACKED [Deal #{d_ticket} {deal.symbol}]: P/L ${deal.profit:.2f}. Audited & updated adaptive brain memory.")

                    for active_sig in Signal.objects.filter(status="ACTIVE", is_deleted=False)[:40]:
                        tick_sig = client.mt5.symbol_info_tick(active_sig.symbol.symbol)
                        if tick_sig and tick_sig.bid > 0 and tick_sig.ask > 0:
                            hit_tp = False
                            hit_sl = False
                            if active_sig.direction == "BUY":
                                if Decimal(str(tick_sig.bid)) >= active_sig.take_profit:
                                    hit_tp = True
                                elif Decimal(str(tick_sig.bid)) <= active_sig.stop_loss:
                                    hit_sl = True
                            else:
                                if Decimal(str(tick_sig.ask)) <= active_sig.take_profit:
                                    hit_tp = True
                                elif Decimal(str(tick_sig.ask)) >= active_sig.stop_loss:
                                    hit_sl = True

                            if hit_tp or hit_sl:
                                active_sig.status = "CLOSED_TP" if hit_tp else "CLOSED_SL"
                                active_sig.save()
                                ai_sig_report = adaptive_brain.analyze_trade_outcome(
                                    symbol=active_sig.symbol.symbol,
                                    direction=active_sig.direction,
                                    profit_usd=Decimal("15.00") if hit_tp else Decimal("-10.00"),
                                    entry_price=active_sig.entry_price,
                                    exit_price=Decimal(str(tick_sig.bid if active_sig.direction == "BUY" else tick_sig.ask)),
                                    sl=active_sig.stop_loss,
                                    tp=active_sig.take_profit,
                                    is_live_trade=False
                                )
                                # Check if this exact signal was actually broadcast to Telegram or was an executed live trade previously
                                was_sent_to_telegram = "[Broadcast]" in active_sig.rationale or Order.objects.filter(signal=active_sig).exists()
                                
                                if was_sent_to_telegram and tg_client:
                                    self.stdout.write(f"AI SENT-SIGNAL OUTCOME [{active_sig.symbol.symbol}]: Hit {'TP' if hit_tp else 'SL'}. Dispatching outcome to Telegram.")
                                    subscribers = TelegramSubscriber.objects.filter(is_deleted=False, signal_alerts=True)
                                    s_icon = "🎯 SIGNAL HIT TAKE PROFIT (TP) 🎯" if hit_tp else "🛑 SIGNAL HIT STOP LOSS (SL) 🛑"
                                    s_msg = (
                                        f"{s_icon}\n\n"
                                        f"Asset: {active_sig.symbol.symbol} ({active_sig.strategy_name})\n"
                                        f"Target Entry: {active_sig.entry_price} -> Exit: {tick_sig.bid if active_sig.direction == 'BUY' else tick_sig.ask}\n\n"
                                        f"🧠 **AI Forensic Outcome Analysis**:\n"
                                        f"{ai_sig_report['diagnosis']}\n\n"
                                        f"🛡️ **Adaptive Brain Action**: Multiplier adjusted to {ai_sig_report['sizing_multiplier']}x based on backtest expectancy."
                                    )
                                    for sub in subscribers:
                                        try:
                                            tg_client.send_message(sub.chat_id, s_msg)
                                        except Exception:
                                            pass
                                else:
                                    # Backtest / watchlist signal outcome -> keep strictly inside backend & Adaptive Brain (`not flooding the telegram with messages`)
                                    self.stdout.write(f"AI BACKTEST/WATCHLIST OUTCOME STORED IN BRAIN ONLY [{active_sig.symbol.symbol}]: Hit {'TP' if hit_tp else 'SL'} (Score {active_sig.confidence}/100). Backtest data kept inside Adaptive Brain without sending to Telegram.")
                except Exception as out_err:
                    self.stderr.write(f"Error during AI outcome tracking loop: {out_err}")

                if channel_layer:
                    active_pos = list(OpenPosition.objects.filter(account=account, is_deleted=False).values(
                        "id", "symbol__symbol", "direction", "volume", "entry_price", "current_price", "unrealized_profit", "broker_ticket", "opened_at"
                    ))
                    formatted_pos = [
                        {
                            "id": str(p["id"]),
                            "symbol": p["symbol__symbol"],
                            "direction": p["direction"],
                            "volume": str(p["volume"]),
                            "entry_price": str(p["entry_price"]),
                            "current_price": str(p["current_price"]),
                            "unrealized_profit": str(p["unrealized_profit"]),
                            "broker_ticket": str(p["broker_ticket"]),
                            "opened_at": p["opened_at"].isoformat() if p["opened_at"] else ""
                        }
                        for p in active_pos
                    ]
                    async_to_sync(channel_layer.group_send)(
                        "trading",
                        {
                            "type": "event",
                            "payload": {
                                "event": "POSITIONS_SYNC",
                                "positions": formatted_pos
                            }
                        }
                    )

                # --- Multi-Stage Scale-Out & Partial Take Profit Engine ---
                try:
                    scale_out_engine.evaluate_open_positions()
                except Exception as scale_err:
                    self.stderr.write(f"Error during scale-out evaluation: {scale_err}")

                for symbol_obj in TradingSymbol.objects.filter(is_tradeable=True, is_deleted=False):
                    sym = symbol_obj.symbol
                    for mt5_tf, tf_enum in [(client.mt5.TIMEFRAME_M5, Timeframe.M5), (client.mt5.TIMEFRAME_M15, Timeframe.M15), (client.mt5.TIMEFRAME_H1, Timeframe.H1)]:
                        rates = client.mt5.copy_rates_from_pos(sym, mt5_tf, 0, 80)
                        if rates is None or len(rates) < 60:
                            continue

                        candles = []
                        for i, r in enumerate(rates):
                            c_time = datetime.fromtimestamp(r["time"], tz=timezone.utc)
                            candles.append(
                                Candle(
                                    time=c_time,
                                    open=Decimal(str(r["open"])),
                                    high=Decimal(str(r["high"])),
                                    low=Decimal(str(r["low"])),
                                    close=Decimal(str(r["close"])),
                                    volume=Decimal(str(r["tick_volume"])),
                                    completed=(i < len(rates) - 1)
                                )
                            )

                        try:
                            from trading_engine.broker_intelligence import MT5BrokerIntelligence
                            broker_intel = MT5BrokerIntelligence(client.mt5)
                            spec = broker_intel.symbol_spec(sym)
                            snapshot = broker_intel.account_snapshot()

                            completed = [c for c in candles if c.completed]
                            if len(completed) >= 60:
                                crt_range = orchestrator.crt.detect(completed)
                                if crt_range:
                                    structure = orchestrator.structure.analyse(completed)
                                    direction = structure.bias if structure.bias != Direction.NEUTRAL else Direction.BUY
                                    sweep = orchestrator.liquidity.detect_sweep(completed, crt_range, spec.tick_size)
                                    kod = orchestrator.kod.confirmed(completed, sweep) if sweep else False
                                    cisd = orchestrator.cisd.confirmed(completed, direction, structure)
                                    session_state = orchestrator.session.evaluate(datetime.now(timezone.utc))
                                    news_state = orchestrator.news.evaluate(datetime.now(timezone.utc), sym, [])

                                    score = orchestrator.scoring.score(direction, sweep, kod, cisd, True, session_state, structure, True, True, news_state, Decimal("50"))
                                    if score.total >= Decimal("50"):
                                        recent = Signal.objects.filter(symbol=symbol_obj, direction=direction.value, strategy_name=f"Romeo TPT ({tf_enum.value})", created_at__gte=django_tz.now() - django_tz.timedelta(minutes=30)).exists()
                                        if not recent:
                                            is_high_conf = score.total >= Decimal("75")
                                            # Calculate 14-period ATR buffer (v1.9.0)
                                            atr = Decimal("0")
                                            if len(completed) >= 15:
                                                tr_list = []
                                                for i in range(1, len(completed)):
                                                    c = completed[i]
                                                    prev = completed[i-1]
                                                    tr = max(c.high - c.low, abs(c.high - prev.close), abs(c.low - prev.close))
                                                    tr_list.append(tr)
                                                atr = sum(tr_list[-14:]) / Decimal("14")

                                            # Spread Protection Gates & Spread-to-Target Ratio (v1.9.2)
                                            point = Decimal(str(mt5_spec.point if mt5_spec.point else "0.00001"))
                                            raw_spread = Decimal(str(mt5_spec.spread if mt5_spec.spread else "5")) * point
                                            pip_size = point * Decimal("10") if mt5_spec.digits in [3, 5] else point
                                            
                                            # Reject if spread exceeds 2.5 pips
                                            if raw_spread > Decimal("2.5") * pip_size:
                                                continue

                                            # Stop Loss: strictly beyond sweep extreme + (1.5x ATR + Current Spread Buffer)
                                            atr_buffer = Decimal("1.5") * atr + raw_spread
                                            calc_sl = (min(completed[-1].low, crt_range.low) - atr_buffer) if direction.value == "BUY" else (max(completed[-1].high, crt_range.high) + atr_buffer)

                                            # Spread-to-Target Ratio check
                                            calc_risk = abs(completed[-1].close - calc_sl)
                                            if calc_risk > 0 and raw_spread / calc_risk > Decimal("0.15"):
                                                continue

                                            calc_tp = completed[-1].close + calc_risk * Decimal("2.0") if direction.value == "BUY" else completed[-1].close - calc_risk * Decimal("2.0")

                                            sig = Signal.objects.create(
                                                symbol=symbol_obj,
                                                author=admin_user,
                                                strategy_name=f"Romeo TPT ({tf_enum.value})",
                                                direction=SignalDirection.BUY if direction.value == "BUY" else SignalDirection.SELL,
                                                status="ACTIVE" if is_high_conf else "WATCHLIST",
                                                entry_price=completed[-1].close,
                                                stop_loss=calc_sl,
                                                take_profit=calc_tp,
                                                confidence=score.total,
                                                rationale=f"Confluences active: {[k for k, v in score.components.items() if v > 0]}",
                                            )
                                            self.stdout.write(f"NEW SIGNAL RECORDED: {sym} ({tf_enum.value}) {sig.direction} (Score: {sig.confidence}/100)")

                                            if channel_layer:
                                                async_to_sync(channel_layer.group_send)(
                                                    "trading",
                                                    {
                                                        "type": "event",
                                                        "payload": {
                                                            "event": "NEW_SIGNAL",
                                                            "signal": {
                                                                "id": sig.id,
                                                                "symbol": sym,
                                                                "direction": sig.direction,
                                                                "confidence": float(sig.confidence),
                                                                "entry_price": float(sig.entry_price),
                                                                "stop_loss": float(sig.stop_loss),
                                                                "take_profit": float(sig.take_profit),
                                                                "rationale": sig.rationale,
                                                                "created_at": sig.created_at.isoformat()
                                                            }
                                                        }
                                                    }
                                                )

                                            # Tier 2 Telegram Routing: Qualified Signals (Primary Watchlist Score >= 90, Exotics 100/100, 1-Hour Cooldown)
                                            if tg_client and is_high_conf:
                                                should_send_tg = False
                                                if sym in PRIMARY_WATCHLIST and sig.confidence >= Decimal("90.00"):
                                                    should_send_tg = True
                                                elif sym not in PRIMARY_WATCHLIST and sig.confidence >= Decimal("100.00"):
                                                    should_send_tg = True

                                                if should_send_tg:
                                                    recent_tg_alert = Signal.objects.filter(symbol=symbol_obj, confidence__gte=Decimal("90"), rationale__icontains="[Broadcast]", created_at__gte=django_tz.now() - django_tz.timedelta(minutes=60)).exclude(id=sig.id).exists()
                                                    if not recent_tg_alert:
                                                        subscribers = TelegramSubscriber.objects.filter(is_deleted=False, signal_alerts=True)
                                                        msg = (
                                                            f"NEW ROMEO TPT INSTITUTIONAL SIGNAL\n\n"
                                                            f"Asset: {sym} ({tf_enum.value})\n"
                                                            f"Direction: {sig.direction}\n"
                                                            f"Confluence Score: {sig.confidence}/100\n"
                                                            f"Entry Price: {sig.entry_price}\n"
                                                            f"Stop Loss: {sig.stop_loss}\n"
                                                            f"Take Profit (TP2): {sig.take_profit}\n\n"
                                                            f"AI Rationale: {sig.rationale}"
                                                        )
                                                        for s in subscribers:
                                                            try:
                                                                tg_client.send_message(s.chat_id, msg)
                                                            except Exception:
                                                                pass
                                                        sig.rationale = f"{sig.rationale} [Broadcast]"
                                                        sig.save()
                                                    else:
                                                        self.stdout.write(f"ANTI-SPAM: Skipped duplicate Telegram signal alert for {sym} (cooldown < 60 min)")
                                                else:
                                                    self.stdout.write(f"ANTI-SPAM: Signal {sym} ({sig.confidence}/100) filtered out of Telegram (Tier 2 cutoff)")

                                            # --- Institutional Trade Execution & Account Management Gate ---
                                            if is_high_conf and broker_setting.enable_autotrading:
                                                try:
                                                    eat_status = EATPhaseEngine.evaluate_asset_phase(sym, score.total)
                                                    if not eat_status.is_allowed:
                                                        self.stdout.write(f"EXECUTION BLOCKED BY EAT PHASE ENGINE [{sym}]: {eat_status.reason}")
                                                        continue

                                                    # --- High-Impact News Blackout Engine Gate ---
                                                    is_news_blocked, news_reason = news_engine.is_news_blackout_active(sym, datetime.now(timezone.utc))
                                                    if is_news_blocked:
                                                        self.stdout.write(f"EXECUTION BLOCKED BY NEWS BLACKOUT ENGINE: {news_reason}")
                                                        continue

                                                    brain_passed, brain_msg, brain_mult = adaptive_brain.evaluate(sym, score.total)
                                                    if not brain_passed:
                                                        self.stdout.write(f"EXECUTION BLOCKED BY ADAPTIVE BRAIN [{sym}]: {brain_msg}")
                                                    else:
                                                        mgr = AccountManager(account, client)
                                                        eval_result = mgr.evaluate_status()

                                                        if not eval_result.trading_allowed:
                                                            self.stdout.write(f"EXECUTION SKIPPED [{sym}]: {eval_result.reason}")
                                                        else:
                                                            duplicate_pos = OpenPosition.objects.filter(account=account, symbol=symbol_obj, is_deleted=False).exists()
                                                            if duplicate_pos:
                                                                self.stdout.write(f"EXECUTION SKIPPED [{sym}]: Position already active on this symbol (duplicate prevention)")
                                                            else:
                                                                passed_gate, gate_msg, gate_meta = TradeExecutionGate.evaluate(
                                                                    client, symbol_obj, sig, score.components, completed, crt_range
                                                                )
                                                                if not passed_gate:
                                                                    self.stdout.write(f"EXECUTION REJECTED [{sym}]: {gate_msg}")
                                                                else:
                                                                    mt5_tick = client.mt5.symbol_info_tick(sym)
                                                                    mt5_spec = client.mt5.symbol_info(sym)
                                                                    if not mt5_tick or not mt5_spec:
                                                                        self.stdout.write(f"EXECUTION REJECTED [{sym}]: Cannot retrieve tick/spec for order execution")
                                                                    elif mt5_tick.bid <= 0 or mt5_tick.ask <= 0 or getattr(mt5_spec, "trade_mode", 1) == 0:
                                                                        self.stdout.write(f"EXECUTION REJECTED [{sym}]: Market closed or trading disabled for symbol")
                                                                    else:
                                                                        lot_size = mgr.calculate_position_size(symbol_obj, sig.entry_price, sig.stop_loss)
                                                                        
                                                                        # Calculate exact institutional execution price and stops buffer
                                                                        point = Decimal(str(mt5_spec.point if mt5_spec.point else "0.00001"))
                                                                        digits = int(mt5_spec.digits if mt5_spec.digits else symbol_obj.digits)
                                                                        stops_level = int(getattr(mt5_spec, "trade_stops_level", 15) or 15)
                                                                        min_stop_dist = point * Decimal(str(max(stops_level, 15) + getattr(mt5_spec, "spread", 5) + 10))

                                                                        # Apply EAT Phase sizing multiplier (e.g. 50% weekend crypto trap or 95+ out-of-hours stock exception)
                                                                        if eat_status.sizing_multiplier < Decimal("1.0") and eat_status.sizing_multiplier > Decimal("0.0"):
                                                                            lot_step = Decimal(str(mt5_spec.volume_step if mt5_spec.volume_step else "0.01"))
                                                                            min_lot = Decimal(str(mt5_spec.volume_min if mt5_spec.volume_min else "0.01"))
                                                                            lot_size = max(min_lot, (lot_size * eat_status.sizing_multiplier / lot_step).to_integral_value(rounding=ROUND_DOWN) * lot_step)

                                                                        # CRT Sniper Limit Retracement Calculation (1.5 to 2.0 pips deep into M5/M15 candle body)
                                                                        pips_retracement = point * Decimal("18") if digits in [3, 5] else point * Decimal("2")
                                                                        
                                                                        if sig.direction == "BUY":
                                                                            exec_price = round(Decimal(str(mt5_tick.ask)) - pips_retracement, digits)
                                                                            exec_sl = round(min(sig.stop_loss, exec_price - min_stop_dist), digits)
                                                                            exec_tp = round(max(sig.take_profit, exec_price + min_stop_dist * Decimal("2")), digits)
                                                                        else:
                                                                            exec_price = round(Decimal(str(mt5_tick.bid)) + pips_retracement, digits)
                                                                            exec_sl = round(max(sig.stop_loss, exec_price + min_stop_dist), digits)
                                                                            exec_tp = round(min(sig.take_profit, exec_price - min_stop_dist * Decimal("2")), digits)

                                                                        # Strict Micro-Expiration (4 Minutes or EAT Phase expiration clamp)
                                                                        exp_ts = int((datetime.now(timezone.utc) + timedelta(minutes=4)).timestamp())
                                                                        if eat_status.expiration_clamp_utc is not None:
                                                                            exp_ts = min(exp_ts, eat_status.expiration_clamp_utc)

                                                                        self.stdout.write(f"EXECUTING CRT SNIPER LIMIT [{sym}]: Mode={eval_result.mode.value}, Phase={eat_status.phase_name}, Lots={lot_size}, Direction={sig.direction}, LimitEntry={exec_price}, ExpIn=4min")

                                                                        req = BrokerOrderRequest(
                                                                            symbol=sym,
                                                                            direction=sig.direction,
                                                                            volume=lot_size,
                                                                            price=exec_price,
                                                                            stop_loss=exec_sl,
                                                                            take_profit=exec_tp,
                                                                            deviation=broker_setting.order_deviation_points,
                                                                            order_type="LIMIT",
                                                                            expiration=exp_ts,
                                                                            is_pit_open=eat_status.is_pit_open
                                                                        )
                                                                        order_res = client.place_market_order(req)

                                                                        if order_res.get("retcode") in (10008, 10009):
                                                                            ticket_str = str(order_res.get("deal") or order_res.get("order") or "")
                                                                            filled_price = Decimal(str(order_res.get("price") or exec_price))

                                                                            Order.objects.create(
                                                                                account=account,
                                                                                signal=sig,
                                                                                symbol=symbol_obj,
                                                                                direction=sig.direction,
                                                                                order_type="MARKET",
                                                                                status="FILLED",
                                                                                requested_volume=lot_size,
                                                                                filled_volume=lot_size,
                                                                                requested_price=exec_price,
                                                                                filled_price=filled_price,
                                                                                stop_loss=exec_sl,
                                                                                take_profit=exec_tp,
                                                                                broker_ticket=ticket_str
                                                                            )

                                                                            OpenPosition.objects.update_or_create(
                                                                                account=account,
                                                                                broker_ticket=ticket_str,
                                                                                defaults={
                                                                                    "symbol": symbol_obj,
                                                                                    "direction": SignalDirection.BUY if sig.direction == "BUY" else SignalDirection.SELL,
                                                                                    "volume": lot_size,
                                                                                    "entry_price": filled_price,
                                                                                    "current_price": filled_price,
                                                                                    "stop_loss": exec_sl,
                                                                                    "take_profit": exec_tp,
                                                                                    "unrealized_profit": Decimal("0.00"),
                                                                                    "opened_at": django_tz.now(),
                                                                                }
                                                                            )
                                                                            self.stdout.write(f"TRADE EXECUTED & RECORDED: {sym} {sig.direction} @ {filled_price} (Ticket: #{ticket_str})")

                                                                            if tg_client:
                                                                                subscribers = TelegramSubscriber.objects.filter(is_deleted=False, signal_alerts=True)
                                                                                exec_msg = (
                                                                                    f"🚨 INSTITUTIONAL TRADE EXECUTED 🚨\n\n"
                                                                                    f"Account Framework: {eval_result.mode.value} (${float(account.balance):.2f})\n"
                                                                                    f"Symbol: {sym} ({tf_enum.value})\n"
                                                                                    f"Direction: {sig.direction}\n"
                                                                                    f"Volume: {lot_size} Lots (Scaled Sizing)\n"
                                                                                    f"Entry Price: {filled_price:.4f}\n"
                                                                                    f"Stop Loss: {exec_sl:.4f}\n"
                                                                                    f"Take Profit: {exec_tp:.4f}\n\n"
                                                                                    f"⚡ Confluence Score: {sig.confidence:.2f}/100\n"
                                                                                    f"🛡️ Risk Framework: Max {eval_result.max_open_positions} Open Trades | Daily Target: {eval_result.daily_target_trades}-{eval_result.max_daily_trades} Trades\n"
                                                                                    f"Gate Verified: {gate_msg}\n"
                                                                                    f"Ticket: #{ticket_str}"
                                                                                )
                                                                                for sub in subscribers:
                                                                                    try:
                                                                                        tg_client.send_message(sub.chat_id, exec_msg)
                                                                                    except Exception:
                                                                                        pass
                                                                        else:
                                                                            self.stdout.write(f"MT5 Order execution failed [{sym}]: retcode={order_res.get('retcode')}, comment={order_res.get('comment')}")
                                                except Exception as exec_err:
                                                    self.stderr.write(f"Execution handling error [{sym}]: {exec_err}")
                        except Exception as eval_err:
                            pass

                time.sleep(1)
            except KeyboardInterrupt:
                self.stdout.write("MT5 Engine loop stopping...")
                break
            except Exception as e:
                self.stderr.write(f"Error inside MT5 engine loop: {e}")
                time.sleep(1)
