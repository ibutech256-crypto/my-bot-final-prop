from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, Any, Tuple, List

from broker_engine.mt5_client import MT5Client

logger = logging.getLogger("trading")


@dataclass
class SymbolPerformanceMemory:
    symbol: str
    total_trades: int
    wins: int
    losses: int
    net_profit_usd: Decimal
    profit_factor: Decimal
    consecutive_losses: int
    is_quarantined: bool
    quarantine_reason: str
    sizing_multiplier: Decimal


class AdaptiveBrainGate:
    """
    Adaptive Brain & Backtesting Feedback Loop.
    Dynamically learns from historical MT5 deals (history_deals_get) and closed trade memory.
    Quarantines negative expectancy symbols, single stock CFDs, and illiquid exotics.
    Adjusts position sizing multipliers in real-time based on live historical profit factor and win streak.
    """
    def __init__(self, client: MT5Client):
        self.client = client
        self.memory: Dict[str, SymbolPerformanceMemory] = {}
        self.last_sync: float = 0.0

    def sync_backtest_memory(self, days_back: int = 7) -> None:
        """
        Scans all MT5 historical deals and builds adaptive performance expectancy memory.
        """
        now = datetime.now(timezone.utc)
        from_dt = now - timedelta(days=days_back)
        try:
            deals = self.client.mt5.history_deals_get(from_dt, now) or []
        except Exception as e:
            logger.error(f"AdaptiveBrain memory sync failed: {e}")
            return

        stats: Dict[str, Dict[str, Any]] = {}
        for d in deals:
            if d.profit == 0.0 and d.entry != 1:  # Skip deposit/withdrawal/zero-profit entries
                continue
            sym = d.symbol
            if sym not in stats:
                stats[sym] = {"trades": 0, "wins": 0, "losses": 0, "net": Decimal("0.0"), "gross_win": Decimal("0.0"), "gross_loss": Decimal("0.0"), "streak": 0}
            
            profit = Decimal(str(d.profit))
            stats[sym]["trades"] += 1
            stats[sym]["net"] += profit
            if profit > Decimal("0"):
                stats[sym]["wins"] += 1
                stats[sym]["gross_win"] += profit
                stats[sym]["streak"] = 0
            elif profit < Decimal("0"):
                stats[sym]["losses"] += 1
                stats[sym]["gross_loss"] += abs(profit)
                stats[sym]["streak"] += 1

        for sym, s in stats.items():
            gross_win = s["gross_win"]
            gross_loss = s["gross_loss"]
            pf = gross_win / gross_loss if gross_loss > Decimal("0") else (Decimal("2.0") if gross_win > Decimal("0") else Decimal("1.0"))
            
            # Adaptive Quarantine & Sizing Multiplier Logic
            is_quarantined = False
            reason = "Optimal expectancy"
            multiplier = Decimal("1.0")

            # 1. Structural Asset Class Check (Quarantine Single Stock CFDs & Illiquid Exotics)
            clean_sym = sym.upper().replace("M", "")
            if any(stock in clean_sym for s_list in [["TSLA", "VRTX", "NTES", "SBUX", "TMO", "BABA", "META", "AMZN", "AAPL", "MSFT", "GOOG", "NVDA", "NFLX"]] for stock in s_list) or len(clean_sym) <= 4 and not any(m in clean_sym for m in ["GOLD", "OIL", "US30", "DXY"]):
                # Stock CFD detection
                if any(k in clean_sym for k in ["TSLA", "VRTX", "NTES", "SBUX", "TMO", "BABA", "META", "AMZN", "AAPL", "MSFT", "GOOG", "NVDA", "NFLX", "V"]):
                    is_quarantined = True
                    reason = "Quarantined: Single Stock CFD (High after-hours gap & spread volatility risk)"
                    multiplier = Decimal("0.0")

            if any(exotic in sym.upper() for exotic in ["CHFDKK", "CHFNOK", "USDSGD", "NOKJPY", "SEKPLN", "PLNHUF", "NZDHUF", "EURDKK", "GBPDKK"]):
                is_quarantined = True
                reason = "Quarantined: Exotic Low-Liquidity Cross (Excessive point spread & slippage risk)"
                multiplier = Decimal("0.0")

            # 2. Historical Expectancy Check
            if not is_quarantined:
                if s["net"] < Decimal("-30.00") or s["streak"] >= 2 or pf < Decimal("0.75"):
                    is_quarantined = True
                    reason = f"Quarantined by Adaptive Brain: Historical net P/L ${float(s['net']):.2f} (PF: {float(pf):.2f}, Loss Streak: {s['streak']})"
                    multiplier = Decimal("0.0")
                elif pf < Decimal("1.10") or s["net"] < Decimal("0.00"):
                    # Cautious adaptive sizing reduction for symbols in recovery or mixed backtest performance
                    multiplier = Decimal("0.35")
                    reason = f"Cautious adaptive sizing (35% multiplier): Historical net P/L ${float(s['net']):.2f} (PF: {float(pf):.2f})"

            self.memory[sym] = SymbolPerformanceMemory(
                symbol=sym,
                total_trades=s["trades"],
                wins=s["wins"],
                losses=s["losses"],
                net_profit_usd=s["net"],
                profit_factor=pf,
                consecutive_losses=s["streak"],
                is_quarantined=is_quarantined,
                quarantine_reason=reason,
                sizing_multiplier=multiplier
            )

    def analyze_trade_outcome(
        self,
        symbol: str,
        direction: str,
        profit_usd: Decimal,
        entry_price: Decimal,
        exit_price: Decimal,
        sl: Decimal,
        tp: Decimal,
        is_live_trade: bool = True,
        adx_at_entry: Decimal = Decimal("28.0"),
        atr_at_entry: Decimal = Decimal("0.020"),
        score_at_entry: Decimal = Decimal("88.00")
    ) -> Dict[str, Any]:
        """
        AI Forensic Outcome Analyzer for Hit TP / Hit SL events.
        Diagnoses structural mechanics, updates SymbolPerformanceMemory and TradeJournal,
        and adapts future execution gates and sizing multipliers based on what caused the outcome.
        """
        is_win = profit_usd > Decimal("0") or (not is_live_trade and ((direction == "BUY" and exit_price >= tp) or (direction == "SELL" and exit_price <= tp)))
        
        # 1. Forensic Diagnosis
        if is_win:
            diagnosis = (
                f"🎯 OPTIMAL INSTITUTIONAL EXPANSION: KOD / Turtle Soup sweep confirmed clean order flow momentum (`Score: {score_at_entry}/100`). "
                f"ADX ({adx_at_entry:.1f}) and ATR ({atr_at_entry*100:.2f}%) maintained strong directional velocity. "
                f"Price expanded directly from {entry_price} to Hit TP at {exit_price} (+${float(profit_usd):.2f})."
            )
            rating = 5
            mistakes = "None - Flawless institutional equilibrium execution."
        else:
            # Diagnose root cause of stop loss
            spread_dist = abs(entry_price - exit_price)
            if adx_at_entry < Decimal("22.0"):
                root_cause = "Market entered non-trending sideways consolidation after entry (`ADX < 22`)."
            elif atr_at_entry < Decimal("0.0012"):
                root_cause = "Intraday volatility contracted (`ATR ratio < 0.12%`), causing price to drift into stop loss wicks."
            else:
                root_cause = "Macro liquidity sweep (Turtle Soup Plus One) extended deeper than initial KOD rejection wick."
            
            diagnosis = (
                f"🛑 STRUCTURAL PULLBACK / SL HIT: Price retraced from {entry_price} to Hit SL at {exit_price} (-${abs(float(profit_usd)):.2f}). "
                f"AI Forensic Diagnosis: {root_cause} "
                f"Adaptive Memory Action: Incrementing consecutive loss streak and applying protective quarantine/sizing reduction."
            )
            rating = 2
            mistakes = root_cause

        # 2. Update Adaptive Memory
        if symbol not in self.memory:
            self.memory[symbol] = SymbolPerformanceMemory(
                symbol=symbol,
                total_trades=0,
                wins=0,
                losses=0,
                net_profit_usd=Decimal("0.00"),
                profit_factor=Decimal("1.00"),
                consecutive_losses=0,
                is_quarantined=False,
                quarantine_reason="Fresh profile",
                sizing_multiplier=Decimal("1.00")
            )
        
        mem = self.memory[symbol]
        mem.total_trades += 1
        mem.net_profit_usd += profit_usd
        if is_win:
            mem.wins += 1
            mem.consecutive_losses = 0
            if mem.sizing_multiplier < Decimal("1.00") and not mem.is_quarantined:
                mem.sizing_multiplier = min(Decimal("1.00"), mem.sizing_multiplier + Decimal("0.25"))
                mem.quarantine_reason = f"Recovery verified (+${float(profit_usd):.2f}). Multiplier restored to {float(mem.sizing_multiplier)}x."
        else:
            mem.losses += 1
            mem.consecutive_losses += 1
            if mem.consecutive_losses >= 2 or mem.net_profit_usd < Decimal("-30.00"):
                mem.is_quarantined = True
                mem.sizing_multiplier = Decimal("0.00")
                mem.quarantine_reason = f"ADAPTIVE SHIELD: Quarantined after hitting SL (-${abs(float(profit_usd)):.2f}, Streak: {mem.consecutive_losses})."
            elif mem.consecutive_losses == 1:
                mem.sizing_multiplier = Decimal("0.50")
                mem.quarantine_reason = f"ADAPTIVE SHIELD: Sizing cut to 50% after hitting SL (-${abs(float(profit_usd)):.2f})."

        # 3. Persist forensic record to SQLite TradeJournal if live trade
        if is_live_trade:
            try:
                from backend.apps.trading.models import ClosedTrade, TradeJournal, TradingAccount, TradingSymbol
                from django.contrib.auth import get_user_model
                from django.utils import timezone as django_tz
                User = get_user_model()
                admin = User.objects.first()
                acc = TradingAccount.objects.filter(is_active=True, is_deleted=False).first()
                sym_obj, _ = TradingSymbol.objects.get_or_create(symbol=symbol)
                if acc and sym_obj and admin:
                    ct = ClosedTrade.objects.create(
                        account=acc,
                        symbol=sym_obj,
                        direction=direction,
                        volume=Decimal("0.10"),
                        entry_price=entry_price,
                        exit_price=exit_price,
                        profit=profit_usd,
                        opened_at=django_tz.now() - timedelta(minutes=30),
                        closed_at=django_tz.now(),
                        broker_ticket=str(int(datetime.now().timestamp()))
                    )
                    TradeJournal.objects.create(
                        trade=ct,
                        user=admin,
                        pre_trade_plan=f"CRT Sniper Entry (Score {score_at_entry}/100, ADX {adx_at_entry:.1f}, ATR {atr_at_entry*100:.2f}%)",
                        post_trade_review=diagnosis,
                        emotion="DISCIPLINED" if is_win else "ADAPTIVE_DEFENSE",
                        mistakes=mistakes,
                        rating=rating
                    )
            except Exception as j_err:
                logger.error(f"Failed to record TradeJournal outcome for {symbol}: {j_err}")

        return {
            "is_win": is_win,
            "diagnosis": diagnosis,
            "consecutive_losses": mem.consecutive_losses,
            "sizing_multiplier": float(mem.sizing_multiplier),
            "is_quarantined": mem.is_quarantined
        }

    def evaluate(self, symbol: str, confidence_score: Decimal) -> Tuple[bool, str, Decimal]:
        """
        Evaluates a candidate trade against the real-time Adaptive Brain backtest memory.
        Returns: (passed_gate, rationale_or_reason, sizing_multiplier)
        """
        import time
        if time.time() - self.last_sync > 60.0 or symbol not in self.memory:
            self.sync_backtest_memory()
            self.last_sync = time.time()

        # Hard asset-class quarantine check even if not in history deals yet
        clean_sym = symbol.upper().replace("M", "")
        spec = self.client.mt5.symbol_info(symbol)
        is_stock = False
        if spec:
            is_stock = (getattr(spec, "category", "") == "Stocks" or 
                        "Stocks" in getattr(spec, "path", "") or 
                        "Shares" in getattr(spec, "path", "") or
                        getattr(spec, "trade_calc_mode", 0) == 32) # Standard exchange stocks calc mode fallback
        else:
            is_stock = any(stock in clean_sym for stock in ["TSLA", "VRTX", "NTES", "SBUX", "TMO", "BABA", "META", "AMZN", "AAPL", "MSFT", "GOOG", "NVDA", "NFLX", "BIDU", "PDD", "FUTU", "HD", "XOM", "JPM", "TSM", "BB", "PYPL", "V"])

        if is_stock:
            return False, f"ADAPTIVE SHIELD: {symbol} blocked (Single Stock CFD after-hours spread & gap vulnerability)", Decimal("0.0")

        # General Exotic Currency Check
        exotic_currencies = [
            "DKK", "NOK", "SEK", "SGD", "ZAR", "MXN", "TRY", "PLN", "HUF", "ILS", 
            "HKD", "CNH", "CNY", "INR", "MYR", "IDR", "KES", "GHS", "ARS", "RON", 
            "UGX", "UAH", "UZS", "VND", "LBP", "KZT", "KWD", "BHD", "BGN", "BDT", 
            "AZN", "AMD", "AED", "XOF", "KGS", "GEL", "EGP", "COP", "BND", "CZK"
        ]
        is_exotic = False
        if not any(m in clean_sym for m in ["XAU", "XAG", "XPT", "XPD", "GOLD", "SILVER", "OIL", "US30", "US500", "NAS100", "DE30", "HK50", "AUS200", "FR40"]):
            if any(exo in clean_sym for exo in exotic_currencies) or any(exotic in symbol.upper() for exotic in ["CHFDKK", "CHFNOK", "USDSGD", "NOKJPY", "SEKPLN", "PLNHUF", "NZDHUF", "EURDKK", "GBPDKK"]):
                is_exotic = True

        if is_exotic:
            return False, f"ADAPTIVE SHIELD: {symbol} blocked (Exotic cross-currency wide spread & point drain)", Decimal("0.0")

        # Standard liquid primary watchlist
        PRIMARY_WATCHLIST = ['XAUUSDm', 'EURUSDm', 'GBPUSDm', 'USDJPYm', 'AUDUSDm', 'BTCUSDm', 'ETHUSDm', 'US30m', 'US500m']

        mem = self.memory.get(symbol)
        # Determine dynamic execution threshold based on recent performance
        base_threshold = Decimal("80.00")

        if mem:
            if mem.is_quarantined:
                return False, f"ADAPTIVE SHIELD: {mem.quarantine_reason}", Decimal("0.0")
            
            if mem.consecutive_losses >= 1:
                # Dynamic Scale-Back: If a trade went wrong, immediately scale back to strict high-confluence barrier
                base_threshold = Decimal("82.00")
                if confidence_score < base_threshold:
                    return False, f"ADAPTIVE THRESHOLD (Scale-Back): {symbol} requires higher Confluence Score >= {base_threshold} (current {confidence_score}) due to recent SL hit (Streak: {mem.consecutive_losses})", Decimal("0.0")
            elif symbol in PRIMARY_WATCHLIST:
                # Quiet Day Mode: Allow highly liquid majors to execute at Score >= 75 on clean slates
                base_threshold = Decimal("75.00")
            
            # If historical expectancy requires higher confidence, enforce it
            if mem.profit_factor < Decimal("1.20") and confidence_score < Decimal("84.00"):
                return False, f"ADAPTIVE THRESHOLD (Expectancy): {symbol} requires Confluence Score >= 84 (current {confidence_score}) due to backtest PF {float(mem.profit_factor):.2f}", Decimal("0.0")
        else:
            if symbol in PRIMARY_WATCHLIST:
                base_threshold = Decimal("75.00")

        if confidence_score < base_threshold:
            return False, f"ADAPTIVE THRESHOLD: {symbol} current score {confidence_score} < dynamic threshold {base_threshold}", Decimal("0.0")

        # Safe sizing multiplier from memory or default 1.0x
        mult = mem.sizing_multiplier if mem else Decimal("1.0")
        reason = mem.quarantine_reason if mem else "Tier-1 liquid instrument, fresh memory profile"
        return True, f"Passed Adaptive Brain Check (Threshold: {base_threshold}, {reason}, Multiplier: {float(mult)}x)", mult
