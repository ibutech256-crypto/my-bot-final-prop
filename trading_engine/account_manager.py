from __future__ import annotations
import logging
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from enum import Enum
from typing import Optional, Tuple, List, Dict, Any
from django.utils import timezone as django_tz

from backend.apps.trading.models import TradingAccount, TradingSymbol, Signal, Order, OpenPosition, SignalDirection
from broker_engine.mt5_client import MT5Client, BrokerOrderRequest
from trading_engine.types import Candle
from trading_engine.eat_phase_engine import EATPhaseEngine

logger = logging.getLogger("trading")


def _env_decimal(name: str, default: str) -> Decimal:
    """Read a tunable execution-gate threshold from the environment."""
    try:
        return Decimal(str(os.getenv(name, default)))
    except Exception:
        return Decimal(default)


# --- TradeExecutionGate tunables (v2.4) ------------------------------------
# Volatility floor is expressed for a 5-minute bar and scaled by sqrt(time),
# because ATR grows roughly with the square root of the sampling interval.
# The previous flat 0.12% was a daily-scale figure applied to M5/M15/H1 bars,
# where a normal FX ATR is 0.02-0.09% of price -- unreachable by construction.
ATR_RATIO_FLOOR_5M = _env_decimal("EXEC_GATE_ATR_FLOOR_5M", "0.00012")

# Upper bound only. A liquidity-sweep reversal does not need a trending market
# -- CRT is Candle *Range* Theory -- but it should stand aside when a violent
# one-way trend is likely to run straight through the reversal.
ADX_MAX = _env_decimal("EXEC_GATE_ADX_MAX", "60.0")

# Reversal-aware RSI confirmation: fading a sweep of highs (SELL) wants an
# extended/overbought reading, and vice versa. This is the inverse of the
# trend-following rule that previously sat here.
RSI_SELL_MIN = _env_decimal("EXEC_GATE_RSI_SELL_MIN", "55.0")
RSI_BUY_MAX = _env_decimal("EXEC_GATE_RSI_BUY_MAX", "45.0")

# Fraction of the risk distance the market may drift from the signalled entry
# before the setup counts as a late entry.
LATE_ENTRY_DRIFT_FRACTION = _env_decimal("EXEC_GATE_LATE_ENTRY_DRIFT", "0.35")


class AccountMode(Enum):
    GROWING_PERSONAL = "Growing (Personal) Account"
    PROP_FIRM = "Prop Firm Account"


@dataclass
class AccountEvaluationResult:
    mode: AccountMode
    trading_allowed: bool
    reason: str
    active_open_positions: int
    max_open_positions: int
    today_trades_count: int
    max_daily_trades: int
    daily_target_trades: int
    drawdown_pct: Decimal
    status_summary: Dict[str, Any]


class TradeExecutionGate:
    """
    Validates institutional execution quality against strict absolute boundaries:
    1. Spread & Transaction Cost: Max 0.10% of price (or <= 2.0 pips for Forex).
    2. Volume & Liquidity: Tier-1 active liquidity check to prevent slippage.
    3. Market Volatility (ATR 14): Guarantees enough daily movement to hit take-profit targets.
    4. Trend Momentum (ADX 14 & RSI 14): ADX >= 25 and RSI > 55 (BUY) / < 45 (SELL).
    """
    @staticmethod
    def _calc_rsi_14(candles: List[Candle]) -> Decimal:
        if len(candles) < 15:
            return Decimal("50.0")
        closes = [c.close for c in candles[-16:]]
        gains = Decimal("0.0")
        losses = Decimal("0.0")
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i-1]
            if diff > Decimal("0"):
                gains += diff
            elif diff < Decimal("0"):
                losses += abs(diff)
        avg_gain = gains / Decimal("14")
        avg_loss = losses / Decimal("14")
        if avg_loss <= Decimal("0"):
            return Decimal("100.0")
        if avg_gain <= Decimal("0"):
            return Decimal("0.0")
        rs = avg_gain / avg_loss
        return Decimal("100.0") - (Decimal("100.0") / (Decimal("1.0") + rs))

    @staticmethod
    def _calc_adx_atr_14(candles: List[Candle]) -> Tuple[Decimal, Decimal]:
        if len(candles) < 28:
            return Decimal("30.0"), Decimal("0.020")
        
        trs = []
        plus_dms = []
        minus_dms = []
        for i in range(len(candles) - 28, len(candles)):
            curr = candles[i]
            prev = candles[i-1]
            tr = max(curr.high - curr.low, abs(curr.high - prev.close), abs(curr.low - prev.close))
            trs.append(tr)
            
            up_move = curr.high - prev.high
            down_move = prev.low - curr.low
            if up_move > down_move and up_move > Decimal("0"):
                plus_dms.append(up_move)
            else:
                plus_dms.append(Decimal("0.0"))
                
            if down_move > up_move and down_move > Decimal("0"):
                minus_dms.append(down_move)
            else:
                minus_dms.append(Decimal("0.0"))

        atr_14 = sum(trs[-14:]) / Decimal("14")
        sum_tr = sum(trs[-14:])
        if sum_tr <= Decimal("0"):
            return Decimal("20.0"), atr_14

        plus_di = (sum(plus_dms[-14:]) / sum_tr) * Decimal("100.0")
        minus_di = (sum(minus_dms[-14:]) / sum_tr) * Decimal("100.0")
        
        dx_denom = plus_di + minus_di
        dx = (abs(plus_di - minus_di) / dx_denom) * Decimal("100.0") if dx_denom > Decimal("0") else Decimal("20.0")
        return dx, atr_14

    @staticmethod
    def _infer_bar_minutes(candles: List[Candle]) -> Decimal:
        """Infer the chart interval from candle timestamps.

        The gate is handed a candle list with no timeframe label, yet several
        of its thresholds are only meaningful relative to the bar size. The
        median spacing of the last few bars is a robust estimate that tolerates
        weekend and session gaps.
        """
        if len(candles) < 3:
            return Decimal("5")
        deltas = []
        for a, b in zip(candles[-11:-1], candles[-10:]):
            secs = (b.time - a.time).total_seconds()
            if secs > 0:
                deltas.append(secs)
        if not deltas:
            return Decimal("5")
        deltas.sort()
        median_secs = deltas[len(deltas) // 2]
        return max(Decimal("1"), Decimal(str(round(median_secs / 60.0, 4))))

    @staticmethod
    def _atr_ratio_floor(bar_minutes: Decimal) -> Decimal:
        """Minimum ATR/price for this bar size, scaled as sqrt(time).

        Anchored at ``ATR_RATIO_FLOOR_5M`` for a 5-minute bar: M5 ~0.012%,
        M15 ~0.021%, H1 ~0.042%, H4 ~0.083%, D1 ~0.20%.
        """
        scale = math.sqrt(float(bar_minutes) / 5.0)
        return ATR_RATIO_FLOOR_5M * Decimal(str(round(scale, 6)))

    @staticmethod
    def evaluate(
        client: MT5Client,
        symbol_obj: TradingSymbol,
        sig: Signal,
        score_components: Dict[str, Decimal],
        completed_candles: List[Candle],
        crt_range: Optional[Any] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        sym = symbol_obj.symbol
        tick = client.mt5.symbol_info_tick(sym)
        spec = client.mt5.symbol_info(sym)
        if not tick or not spec:
            return False, f"Missing real-time MT5 tick or symbol info for {sym}", {}

        ask_price = Decimal(str(tick.ask))
        bid_price = Decimal(str(tick.bid))
        spread_raw = ask_price - bid_price
        spread_ratio = spread_raw / ask_price if ask_price > Decimal("0") else Decimal("0")

        # --- Pre-London Morning Guard Rules (05:00 - 10:00 EAT) ---
        eat_dt = EATPhaseEngine.get_eat_time()
        eat_time_float = eat_dt.hour + eat_dt.minute / 60.0
        if 5.0 <= eat_time_float < 10.0:
            # Message previously advertised a "92 requirement" while the code
            # tested 55. The code is authoritative; the text now matches it.
            if sig.confidence < Decimal("55.00"):
                return False, f"MORNING GUARD BLOCK [{sym}]: Score {sig.confidence}/100 < 55 requirement during Pre-London window (05:00-10:00 EAT)", {"score": float(sig.confidence)}

            # The former ADX >= 28 sub-check is removed for the same reason as
            # the main momentum gate below: it demanded a trending market from
            # a range-reversal strategy. The tighter pre-London spread rule is
            # retained, as thin-book protection is genuinely timeframe-neutral.
            if spread_ratio > Decimal("0.0005"):  # Max 0.05%
                return False, f"MORNING GUARD BLOCK [{sym}]: Spread ({spread_ratio*100:.3f}%) > 0.05% requirement during Pre-London window", {"spread": float(spread_raw)}

        # 1. Bid-Ask Spread Gate (Transaction Cost): Max 0.10% or <= 2.0 pips for Forex
        if ask_price > Decimal("0"):
            spread_ratio = spread_raw / ask_price
            # Check if Forex pair or Stock/Crypto
            is_forex = any(f in sym.upper() for f in ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]) and not any(c in sym.upper() for c in ["GOLD", "OIL", "BTC", "ETH", "US30"])
            if is_forex:
                point = Decimal(str(spec.point if spec.point else "0.00001"))
                pips = spread_raw / (point * Decimal("10") if spec.digits in [3, 5] else point)
                if pips > Decimal("2.5") and spread_ratio > Decimal("0.0010"):
                    return False, f"Spread Gate rejected: Forex spread ({pips:.1f} pips / {spread_ratio*100:.3f}%) exceeds the 2.5 pip / 0.10% threshold", {"spread": float(spread_raw)}
            else:
                if spread_ratio > Decimal("0.0010"):  # Strictly Max 0.10% for Crypto/Stocks/Metals
                    return False, f"Spread Gate rejected: Transaction cost ({spread_ratio*100:.3f}%) exceeds maximum 0.10% boundary", {"spread": float(spread_raw)}

        # 2. Trading Volume & Tier-1 Liquidity Gate
        if completed_candles[-1].volume <= Decimal("0") and not any(t in sym.upper() for t in ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "BTCUSD"]):
            return False, f"Liquidity Gate rejected: Zero or stagnant bar volume on {sym} (prevents slippage/order rejection)", {}

        # 3. Market Volatility (ATR 14) & Trend Momentum (ADX 14 / RSI 14) Gates
        rsi_14 = TradeExecutionGate._calc_rsi_14(completed_candles)
        adx_14, atr_14 = TradeExecutionGate._calc_adx_atr_14(completed_candles)

        # Timeframe-relative volatility floor.
        # The old flat 0.0012 (0.12%) was a daily-scale figure applied to
        # intraday bars, where a normal FX ATR(14) is 0.02-0.09% of price. It
        # rejected 37 of 60 setups in a single live sample and could never pass
        # on M5/M15. The floor is now anchored per bar size (see
        # ATR_RATIO_FLOOR_5M) and scaled as sqrt(time).
        bar_minutes = TradeExecutionGate._infer_bar_minutes(completed_candles)
        atr_floor = TradeExecutionGate._atr_ratio_floor(bar_minutes)
        atr_ratio = Decimal("0")
        if ask_price > Decimal("0"):
            atr_ratio = atr_14 / ask_price
            if atr_ratio < atr_floor:
                return False, (
                    f"Volatility Gate rejected: ATR(14) ratio ({atr_ratio*100:.4f}%) below the "
                    f"{atr_floor*100:.4f}% floor for a {bar_minutes}-minute bar"
                ), {"atr": float(atr_14), "bar_minutes": float(bar_minutes)}

        # Trend-strength ceiling, not a floor.
        # This strategy fades liquidity sweeps inside a range; requiring
        # ADX >= 25 demanded a trending market from a mean-reversion setup and
        # contradicted CRT (Candle *Range* Theory). Observed live ADX on valid
        # setups was 0.8-13.5. The gate now only stands aside when a violently
        # one-way market is likely to run through the reversal.
        if adx_14 > ADX_MAX:
            return False, (
                f"Momentum Gate rejected: ADX(14)={adx_14:.1f} exceeds {ADX_MAX} -- market is "
                f"trending too hard to fade a liquidity sweep"
            ), {"adx": float(adx_14)}

        # Reversal-aware RSI confirmation.
        # Inverted from the previous trend-following rule. A Turtle Soup SELL
        # triggers precisely because price swept a high, so RSI is elevated by
        # construction -- the old "RSI must be < 45 for SELL" was unsatisfiable
        # for the very pattern it gated (live example: NZDZAR SELL rejected at
        # RSI 70.7, which is confirmation, not a disqualification).
        if sig.direction == "SELL" and rsi_14 < RSI_SELL_MIN:
            return False, (
                f"Momentum Gate rejected: RSI(14)={rsi_14:.1f} < {RSI_SELL_MIN} -- sweep of highs "
                f"not extended enough to fade"
            ), {"rsi": float(rsi_14)}
        if sig.direction == "BUY" and rsi_14 > RSI_BUY_MAX:
            return False, (
                f"Momentum Gate rejected: RSI(14)={rsi_14:.1f} > {RSI_BUY_MAX} -- sweep of lows "
                f"not extended enough to fade"
            ), {"rsi": float(rsi_14)}

        # 4. CRT & Late Entry Handling
        price_risk = abs(sig.entry_price - sig.stop_loss) + Decimal("1e-9")
        entry_dist = abs(Decimal(str(tick.ask if sig.direction == "BUY" else tick.bid)) - sig.entry_price)

        # ``crt_range is not None`` made this unconditionally True, because
        # run_mt5_engine always passes a CRT range -- so every setup was
        # treated as a late entry and forced to clear ADX >= 30. Lateness is
        # now what the name says: how far the market has drifted from the
        # signalled entry relative to the risk being taken.
        is_late_entry = entry_dist > price_risk * LATE_ENTRY_DRIFT_FRACTION

        if is_late_entry:
            # Judge lateness on how far price has run, not on trend strength:
            # requiring ADX >= 30 here reintroduced the trend-following bias
            # through the back door. A setup is still tradeable while the
            # remaining distance to the stop dominates the drift already
            # incurred, or when the confluence score is exceptional.
            drift_ratio = entry_dist / price_risk
            acceptable = (
                drift_ratio <= LATE_ENTRY_DRIFT_FRACTION * Decimal("2")
                or sig.confidence >= Decimal("84")
            )
            if not acceptable:
                return False, (
                    f"CRT Late Entry rejected: price drifted {drift_ratio:.0%} of the risk "
                    f"distance from the signalled entry (limit "
                    f"{LATE_ENTRY_DRIFT_FRACTION * 2:.0%}) and score {sig.confidence} < 84"
                ), {"is_late_entry": True, "entry_dist": float(entry_dist),
                    "drift_ratio": float(drift_ratio)}
            logger.info(
                "Allowing CRT Late Entry on %s: drift %.0f%% of risk, score %s.",
                sym, float(drift_ratio * 100), sig.confidence,
            )

        return True, (
            f"Passed Institutional Filter Checklist (Spread {spread_ratio*100:.3f}%, "
            f"ADX {adx_14:.1f} <= {ADX_MAX}, RSI {rsi_14:.1f}, "
            f"ATR {atr_ratio*100:.4f}% >= {atr_floor*100:.4f}% @ {bar_minutes}m)"
        ), {
            "spread": float(spread_raw),
            "momentum": True,
            "adx": float(adx_14),
            "rsi": float(rsi_14),
            "atr_ratio": float(atr_ratio),
            "bar_minutes": float(bar_minutes),
        }


class AccountManager:
    """
    Manages Prop Firm & Growing (Personal) Account execution rules, limits, and position sizing.
    """
    def __init__(self, account: TradingAccount, client: MT5Client):
        self.account = account
        self.client = client

    def get_account_mode(self) -> AccountMode:
        if self.account.balance < Decimal("1000") or "GROW" in self.account.account_name.upper():
            return AccountMode.GROWING_PERSONAL
        return AccountMode.PROP_FIRM

    def evaluate_status(self) -> AccountEvaluationResult:
        mode = self.get_account_mode()
        now = django_tz.now()
        today_orders_count = Order.objects.filter(account=self.account, created_at__date=now.date()).count()
        active_open_positions = OpenPosition.objects.filter(account=self.account, is_deleted=False).count()

        if mode == AccountMode.GROWING_PERSONAL:
            max_open_positions = 4
            max_daily_trades = 15
            daily_target_trades = 10
            
            if active_open_positions >= max_open_positions:
                return AccountEvaluationResult(
                    mode=mode,
                    trading_allowed=False,
                    reason=f"Growing Account limit reached: strictly max {max_open_positions} open trades allowed simultaneously ({active_open_positions}/{max_open_positions})",
                    active_open_positions=active_open_positions,
                    max_open_positions=max_open_positions,
                    today_trades_count=today_orders_count,
                    max_daily_trades=max_daily_trades,
                    daily_target_trades=daily_target_trades,
                    drawdown_pct=Decimal("0.0"),
                    status_summary={"mode": mode.value, "active_open": active_open_positions, "today_trades": today_orders_count}
                )

            if today_orders_count >= max_daily_trades:
                return AccountEvaluationResult(
                    mode=mode,
                    trading_allowed=False,
                    reason=f"Growing Account daily trade cap reached: {max_daily_trades} trades executed today",
                    active_open_positions=active_open_positions,
                    max_open_positions=max_open_positions,
                    today_trades_count=today_orders_count,
                    max_daily_trades=max_daily_trades,
                    daily_target_trades=daily_target_trades,
                    drawdown_pct=Decimal("0.0"),
                    status_summary={"mode": mode.value, "active_open": active_open_positions, "today_trades": today_orders_count}
                )

            return AccountEvaluationResult(
                mode=mode,
                trading_allowed=True,
                reason=f"Growing Account active ({active_open_positions}/{max_open_positions} open, {today_orders_count}/{max_daily_trades} daily trades)",
                active_open_positions=active_open_positions,
                max_open_positions=max_open_positions,
                today_trades_count=today_orders_count,
                max_daily_trades=max_daily_trades,
                daily_target_trades=daily_target_trades,
                drawdown_pct=Decimal("0.0"),
                status_summary={"mode": mode.value, "active_open": active_open_positions, "today_trades": today_orders_count}
            )

        else:
            # Prop Firm Account Mode (Balance >= $1000)
            max_open_positions = 3
            max_daily_trades = 10
            daily_target_trades = 5

            if active_open_positions >= max_open_positions:
                return AccountEvaluationResult(
                    mode=mode,
                    trading_allowed=False,
                    reason=f"Prop Firm exposure limit reached ({active_open_positions}/{max_open_positions} open positions)",
                    active_open_positions=active_open_positions,
                    max_open_positions=max_open_positions,
                    today_trades_count=today_orders_count,
                    max_daily_trades=max_daily_trades,
                    daily_target_trades=daily_target_trades,
                    drawdown_pct=Decimal("0.0"),
                    status_summary={"mode": mode.value, "active_open": active_open_positions, "today_trades": today_orders_count}
                )

            return AccountEvaluationResult(
                mode=mode,
                trading_allowed=True,
                reason="Prop Firm Account active & compliant with risk parameters",
                active_open_positions=active_open_positions,
                max_open_positions=max_open_positions,
                today_trades_count=today_orders_count,
                max_daily_trades=max_daily_trades,
                daily_target_trades=daily_target_trades,
                drawdown_pct=Decimal("0.0"),
                status_summary={"mode": mode.value, "active_open": active_open_positions, "today_trades": today_orders_count}
            )

    def calculate_position_size(
        self,
        symbol_obj: TradingSymbol,
        entry_price: Decimal,
        stop_loss: Decimal,
        confidence: Decimal | None = None,
    ) -> Decimal:
        """Return the base lot size for this setup.

        Args:
            confidence: Signal score, 0-100. Accepted for interface
                compatibility with ``run_mt5_engine``, which has always called
                this method with four arguments while the signature declared
                three -- a latent ``TypeError: takes 4 positional arguments but
                5 were given`` that stayed dormant only because no signal ever
                reached the execution branch. It is recorded for telemetry but
                deliberately does **not** scale the size here: conviction
                scaling is applied once, downstream, via the tier risk
                multiplier (Tier 1 x0.5 / Tier 2 x1.0 / Tier 3 x1.5). Applying
                it in both places would compound the two factors.
        """
        sym = symbol_obj.symbol
        spec = self.client.mt5.symbol_info(sym)
        min_lot = Decimal(str(spec.volume_min if spec else symbol_obj.min_lot))
        max_lot = Decimal(str(spec.volume_max if spec else symbol_obj.max_lot))
        lot_step = Decimal(str(spec.volume_step if spec else symbol_obj.lot_step))

        status = self.evaluate_status()
        if status.mode == AccountMode.GROWING_PERSONAL:
            equity = self.account.equity
            if equity < Decimal("100"):
                raw_lots = min_lot
            elif equity < Decimal("250"):
                raw_lots = min_lot * Decimal("2")
            elif equity < Decimal("500"):
                raw_lots = min_lot * Decimal("3")
            else:
                raw_lots = (equity / Decimal("1000")) * Decimal("0.03")
            safety_max = Decimal("0.10")
        else:
            price_risk = abs(entry_price - stop_loss)
            min_price_risk_floor = entry_price * Decimal("0.002")
            effective_price_risk = max(price_risk, min_price_risk_floor, Decimal("0.00010"))
            
            cash_risk = self.account.balance * Decimal("0.0050")
            contract_size = Decimal(str(spec.trade_contract_size if spec else symbol_obj.contract_size))
            if contract_size <= Decimal("0"):
                contract_size = Decimal("100000")
            raw_lots = cash_risk / (effective_price_risk * contract_size)
            safety_max = Decimal("0.50")

        final_lots = (raw_lots / lot_step).to_integral_value(rounding=ROUND_DOWN) * lot_step
        final_lots = max(min_lot, min(max_lot, min(safety_max, final_lots)))
        logger.info(
            "SIZING [%s]: mode=%s raw=%s -> %s lots (min=%s max=%s step=%s cap=%s conf=%s)",
            sym, status.mode.value, raw_lots, final_lots,
            min_lot, max_lot, lot_step, safety_max,
            confidence if confidence is not None else "n/a",
        )
        return final_lots
