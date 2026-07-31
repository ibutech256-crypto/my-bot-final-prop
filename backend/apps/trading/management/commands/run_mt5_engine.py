from __future__ import annotations
import os, sys
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"): sys.stderr.reconfigure(encoding="utf-8", errors="replace")
import time
from datetime import datetime, timezone, timedelta
import json
from decimal import ROUND_DOWN, Decimal
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
from trading_engine.correlation_shield import check_correlation
from trading_engine.htf_bias import HTFBiasEngine, build_mt5_rate_loader
from trading_engine.liquidity import select_sweep_for_displacement
from trading_engine.pipeline_trace import (
    FUNNEL,
    Outcome,
    Reason,
    SignalTrace,
    Stage,
    classify_session,
    describe,
)
from trading_engine.scoring import tier_risk_multiplier
from trading_engine.strategy_config import CONFIG, log_active_configuration
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

# The environment is only fully populated after ``_auto_load_env`` has walked
# up to C:\prop-frim-bot\.env, so the strategy configuration must be re-read
# here; importing it at module scope would capture a pre-dotenv snapshot.
from trading_engine import strategy_config as _strategy_config  # noqa: E402
CONFIG = _strategy_config.reload()

# Shadow mode: run the complete decision funnel against live market data and
# log every trade that *would* be placed, without transmitting any order.
# Enabled with SHADOW_MODE=1 in the environment; surfaced in the startup banner
# so the operating mode is never ambiguous.
SHADOW_MODE = CONFIG.pipeline.shadow_mode

PRIMARY_WATCHLIST = ['XAUUSDm', 'EURUSDm', 'GBPUSDm', 'USDJPYm', 'AUDUSDm', 'BTCUSDm', 'ETHUSDm', 'US30m', 'US500m', 'TSLAm', 'AAPLm', 'NVDAm', 'MSFTm', 'AMZNm', 'GOOGm', 'META', 'PYPLm']

FOCUS_SYMBOLS = ['ADAUSDm', 'AUDCADm', 'AUDCHFm', 'AUDJPYm', 'AUDMXNm', 'AUDNZDm', 'AUDSGDm', 'AUDUSDm', 'AUDZARm', 'AUS200m', 'BCHUSDm', 'BNBUSDm', 'BTCUSDm', 'BTCXAUm', 'CADCHFm', 'CADJPYm', 'CADMXNm', 'CADTRYm', 'CAKEUSDm', 'CHFHUFm', 'CHFJPYm', 'CHFMXNm', 'CHFPLNm', 'CHFSGDm', 'CHFTRYm', 'COMPUSDm', 'DE30m', 'DKKPLNm', 'DOGEUSDm', 'DOTUSDm', 'DXYm', 'ETHBTCm', 'ETHUSDm', 'EURAUDm', 'EURCADm', 'EURCHFm', 'EURCZKm', 'EURDKKm', 'EURGBPm', 'EURHKDm', 'EURHUFm', 'EURJPYm', 'EURMXNm', 'EURNOKm', 'EURNZDm', 'EURPLNm', 'EURSEKm', 'EURTRYm', 'EURUSDm', 'EURZARm', 'FR40m', 'GBPAUDm', 'GBPCADm', 'GBPCHFm', 'GBPHUFm', 'GBPJPYm', 'GBPMXNm', 'GBPNOKm', 'GBPNZDm', 'GBPSEKm', 'GBPTRYm', 'GBPUSDm', 'GBPZARm', 'HK50m', 'HUFJPYm', 'JP225m', 'LINKUSDm', 'LTCUSDm', 'MANAUSDm', 'NZDCADm', 'NZDCHFm', 'NZDHUFm', 'NZDJPYm', 'NZDTRYm', 'NZDUSDm', 'NZDZARm', 'SEKPLNm', 'SOLUSDm', 'UK100m', 'UKOILm', 'US30m', 'US500_x100m', 'US500m', 'USDAEDm', 'USDCADm', 'USDCHFm', 'USDCNHm', 'USDCZKm', 'USDDKKm', 'USDHKDm', 'USDHUFm', 'USDINRm', 'USDISKm', 'USDJPYm', 'USDKWDm', 'USDMADm', 'USDMXNm', 'USDNOKm', 'USDPLNm', 'USDSARm', 'USDSEKm', 'USDSGDm', 'USDTHBm', 'USDTRYm', 'USDTWDm', 'USDZARm', 'USOILm', 'USTEC_x100m', 'USTECm', 'XAGAUDm', 'XAGEURm', 'XAGJPYm', 'XAGUSDm', 'XAUAUDm', 'XAUEURm', 'XAUGBPm', 'XAUUSDm', 'XCUUSDm', 'XPDUSDm', 'XPTUSDm', 'XRPUSDm', 'XZNUSDm']

class Command(BaseCommand):
    help = "Run the real-time MT5 Institutional Trading & Telemetry Engine (Romeo TPT)"

    def handle(self, *args, **options):
        import signal
        try:
            signal.signal(signal.SIGINT, signal.SIG_IGN)
        except Exception:
            pass
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

        # Send instant Trading Engine Startup Alert to Telegram (v1.9.5)
        if tg_client:
            try:
                subscribers = TelegramSubscriber.objects.filter(is_deleted=False, signal_alerts=True)
                start_msg = (
                    f"INSTITUTIONAL TRADING ENGINE STARTED\n\n"
                    f"Status: TradingMT5Engine service online and active.\n"
                    f"MT5 Terminal: Connected (#{login_id} @ {server})\n"
                    f"Time: {django_tz.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                )
                for s in subscribers:
                    tg_client.send_message(s.chat_id, start_msg)
            except Exception:
                pass

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

        # ==================================================================
        # Phase 1 / 4 / 7 wiring: HTF engine, funnel publisher, signal upsert
        # ==================================================================

        # Module 1: real higher-timeframe bias. Previously ``htf_ok`` defaulted
        # to True because this call site never supplied any HTF data at all, so
        # every signal ever scored collected the full 15-point HTF Alignment
        # component. The loader is cached per symbol with a TTL so the extra
        # series cost ~2 IPC calls per symbol per HTF_CACHE_TTL_SECONDS rather
        # than per scan cycle.
        htf_engine = HTFBiasEngine(build_mt5_rate_loader(client.mt5))
        self.stdout.write(
            f"HTF confirmation: timeframes={list(CONFIG.htf.timeframes)} "
            f"bars={CONFIG.htf.bars} ttl={CONFIG.htf.cache_ttl_seconds}s "
            f"require_confirmation={CONFIG.htf.require_confirmation}"
        )

        _TF_LOOKUP = {
            "M1": (client.mt5.TIMEFRAME_M1, Timeframe.M1),
            "M5": (client.mt5.TIMEFRAME_M5, Timeframe.M5),
            "M15": (client.mt5.TIMEFRAME_M15, Timeframe.M15),
            "H1": (client.mt5.TIMEFRAME_H1, Timeframe.H1),
            "H4": (client.mt5.TIMEFRAME_H4, Timeframe.H4),
            "D1": (client.mt5.TIMEFRAME_D1, Timeframe.D1),
        }
        scan_timeframes = [
            _TF_LOOKUP[name] for name in CONFIG.pipeline.scan_timeframes if name in _TF_LOOKUP
        ]
        if not scan_timeframes:
            scan_timeframes = [
                (client.mt5.TIMEFRAME_M5, Timeframe.M5),
                (client.mt5.TIMEFRAME_M15, Timeframe.M15),
                (client.mt5.TIMEFRAME_H1, Timeframe.H1),
            ]

        #: Statuses that must never be overwritten by a refresh.
        TERMINAL_SIGNAL_STATUSES = (
            "EXECUTED", "FILLED", "SHADOW_WOULD_EXECUTE",
            "CLOSED_TP", "CLOSED_SL", "WAITING_ENTRY", "CANCELLED",
        )

        def upsert_signal(*, symbol_obj, tf_value, direction, status, entry, stop_loss,
                          take_profit, score, trace, htf_result, spread_pips, spread_ratio,
                          confluences, block_code, block_reason):
            """Create the Signal row, or refresh the open one already covering it.

            The previous revision inserted a brand-new row on every qualifying
            evaluation and used a 30-minute "does a row already exist?" test to
            throttle. That produced 501 WATCHLIST rows for 121 instruments and,
            far worse, made the throttle a *silent execution blocker* (see the
            execution-cooldown comment in the scan loop).

            Refreshing in place keeps one live row per symbol/direction/
            timeframe, so the dashboard shows current state instead of a
            scrolling history, and the execution decision is made every cycle
            on fresh prices.
            """
            strategy = f"Romeo TPT ({tf_value})"
            cutoff = django_tz.now() - timedelta(minutes=CONFIG.pipeline.signal_refresh_minutes)
            direction_value = "BUY" if direction.value == "BUY" else "SELL"
            fields = dict(
                status=status,
                entry_price=entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=score.total,
                rationale=(
                    f"{score.gate_reason} | confluences: {', '.join(confluences) or 'none'} | "
                    f"HTF {htf_result.status.value} ({htf_result.summary})"
                ),
                timeframe=tf_value,
                tier=score.tier or "",
                lifecycle_stage=trace.stages[-1] if trace.stages else "",
                block_code=block_code,
                block_reason=block_reason,
                htf_status=htf_result.status.value,
                htf_detail=htf_result.summary[:120],
                confluences=", ".join(confluences)[:255],
                spread_pips=spread_pips,
                spread_risk_ratio=spread_ratio,
                lifecycle_json=json.dumps(trace.as_dict(), default=str)[:60000],
            )

            existing = (
                Signal.objects.filter(
                    symbol=symbol_obj,
                    direction=direction_value,
                    strategy_name=strategy,
                    is_deleted=False,
                    created_at__gte=cutoff,
                )
                .exclude(status__in=TERMINAL_SIGNAL_STATUSES)
                .order_by("-created_at")
                .first()
            )
            if existing is not None:
                for key, value in fields.items():
                    setattr(existing, key, value)
                existing.save(update_fields=list(fields.keys()) + ["updated_at"])
                return existing, False

            return (
                Signal.objects.create(
                    symbol=symbol_obj,
                    author=admin_user,
                    strategy_name=strategy,
                    direction=SignalDirection.BUY if direction_value == "BUY" else SignalDirection.SELL,
                    **fields,
                ),
                True,
            )

        def mark_signal_blocked(sig, code, detail=""):
            """Persist a specific, machine-readable block reason on a signal.

            Replaces the previous badge logic, which guessed a status by
            substring-matching the English gate message and fell through to
            ``BLOCKED_RISK_CAP_REACHED`` for anything it did not recognise --
            which is how 80 RSI/ADX/volatility rejections were recorded as
            risk-cap breaches in a single three-hour window.
            """
            Signal.objects.filter(id=sig.id).update(
                status="BLOCKED",
                block_code=code,
                block_reason=describe(code, detail),
                lifecycle_stage=Stage.SIGNAL_PERSISTED.value,
            )

        def broadcast_signal(sig, sym, score, htf_result, spread_pips, created):
            if not channel_layer:
                return
            try:
                async_to_sync(channel_layer.group_send)(
                    "trading",
                    {
                        "type": "event",
                        "payload": {
                            "event": "NEW_SIGNAL" if created else "SIGNAL_UPDATED",
                            "signal": {
                                "id": sig.id,
                                "symbol": sym,
                                "timeframe": sig.timeframe,
                                "direction": sig.direction,
                                "status": sig.status,
                                "tier": sig.tier,
                                "confidence": float(sig.confidence),
                                "entry_price": float(sig.entry_price),
                                "stop_loss": float(sig.stop_loss),
                                "take_profit": float(sig.take_profit),
                                "htf_status": sig.htf_status,
                                "htf_detail": sig.htf_detail,
                                "spread_pips": float(spread_pips),
                                "block_code": sig.block_code,
                                "block_reason": sig.block_reason,
                                "rationale": sig.rationale,
                                "created_at": sig.created_at.isoformat(),
                            },
                        },
                    },
                )
            except Exception as exc:
                logger.warning("Websocket signal broadcast failed for %s: %s", sym, exc)

        def maybe_telegram_signal(sig, sym, tf_enum, symbol_obj):
            """Tier-2 Telegram routing with the original anti-spam behaviour."""
            try:
                should_send = (
                    (sym in PRIMARY_WATCHLIST and sig.confidence >= Decimal("90.00"))
                    or (sym not in PRIMARY_WATCHLIST and sig.confidence >= Decimal("100.00"))
                )
                if not should_send:
                    return
                recent_alert = Signal.objects.filter(
                    symbol=symbol_obj,
                    confidence__gte=Decimal("90"),
                    rationale__icontains="[Broadcast]",
                    created_at__gte=django_tz.now() - timedelta(minutes=60),
                ).exclude(id=sig.id).exists()
                if recent_alert:
                    self.stdout.write(
                        f"ANTI-SPAM: skipped duplicate Telegram alert for {sym} (cooldown < 60 min)")
                    return
                msg = (
                    f"NEW ROMEO TPT INSTITUTIONAL SIGNAL\n\n"
                    f"Asset: {sym} ({tf_enum.value})\n"
                    f"Direction: {sig.direction}\n"
                    f"Tier: {sig.tier or 'n/a'}\n"
                    f"Confluence Score: {sig.confidence}/100\n"
                    f"HTF: {sig.htf_status} ({sig.htf_detail})\n"
                    f"Entry Price: {sig.entry_price}\n"
                    f"Stop Loss: {sig.stop_loss}\n"
                    f"Take Profit (TP2): {sig.take_profit}\n\n"
                    f"AI Rationale: {sig.rationale}"
                )
                for sub in TelegramSubscriber.objects.filter(is_deleted=False, signal_alerts=True):
                    try:
                        tg_client.send_message(sub.chat_id, msg)
                    except Exception:
                        pass
                Signal.objects.filter(id=sig.id).update(rationale=f"{sig.rationale} [Broadcast]")
            except Exception as exc:
                logger.warning("Telegram signal routing failed for %s: %s", sym, exc)

        def notify_execution(sig, sym, tf_enum, eval_result, lot_size, filled_price,
                             exec_sl, exec_tp, gate_msg, ticket_str):
            try:
                msg = (
                    f"INSTITUTIONAL TRADE EXECUTED\n\n"
                    f"Account Framework: {eval_result.mode.value} (${float(account.balance):.2f})\n"
                    f"Symbol: {sym} ({tf_enum.value})\n"
                    f"Direction: {sig.direction}\n"
                    f"Tier: {sig.tier or 'n/a'}\n"
                    f"Volume: {lot_size} Lots\n"
                    f"Entry Price: {filled_price}\n"
                    f"Stop Loss: {exec_sl}\n"
                    f"Take Profit: {exec_tp}\n\n"
                    f"Confluence Score: {sig.confidence}/100\n"
                    f"HTF: {sig.htf_status} ({sig.htf_detail})\n"
                    f"Risk Framework: Max {eval_result.max_open_positions} Open Trades | "
                    f"Daily Target: {eval_result.daily_target_trades}-{eval_result.max_daily_trades}\n"
                    f"Gate Verified: {gate_msg}\n"
                    f"Ticket: #{ticket_str}"
                )
                for sub in TelegramSubscriber.objects.filter(is_deleted=False, signal_alerts=True):
                    try:
                        tg_client.send_message(sub.chat_id, msg)
                    except Exception:
                        pass
            except Exception as exc:
                logger.warning("Telegram execution notification failed for %s: %s", sym, exc)

        def publish_funnel(cycle_no):
            """Log the funnel, write the snapshot and push it to the dashboard."""
            try:
                for line in FUNNEL.render_text().splitlines():
                    logger.info("%s", line)
                snapshot_path = CONFIG.pipeline.funnel_snapshot_path
                if not os.path.isabs(snapshot_path):
                    snapshot_path = str(Path(__file__).resolve().parents[5] / snapshot_path)
                FUNNEL.write_snapshot(snapshot_path)
                if channel_layer:
                    snapshot = FUNNEL.snapshot(include_recent=False)
                    async_to_sync(channel_layer.group_send)(
                        "trading",
                        {
                            "type": "event",
                            "payload": {
                                "event": "FUNNEL_UPDATE",
                                "funnel": {
                                    "scan_cycles": cycle_no,
                                    "current_session": snapshot["current_session"],
                                    "stages": snapshot["cumulative"]["funnel"],
                                    "rejection_reasons": snapshot["cumulative"]["rejection_reasons"][:10],
                                    "outcomes": snapshot["cumulative"]["outcomes"],
                                    "htf_distribution": snapshot["cumulative"]["htf_distribution"],
                                    "tier_distribution": snapshot["cumulative"]["tier_distribution"],
                                    "watchlist_reasons": snapshot["watchlist_reasons"][:60],
                                },
                            },
                        },
                    )
            except Exception as exc:
                logger.warning("Funnel publication failed: %s", exc)

        _mode_banner = (
            "SHADOW MODE -- signals scored and sized, NO orders transmitted"
            if SHADOW_MODE else
            "LIVE MODE -- orders will be transmitted to the broker"
        )
        self.stdout.write(f"*** {_mode_banner} ***")
        logger.warning("Engine starting in %s", _mode_banner)
        # Phase 6: dump the entire effective configuration exactly once, so the
        # active value of every threshold is recoverable from the log alone.
        log_active_configuration(logger)
        self.stdout.write(f"MT5 Real-Time Polling Loop active tracking {len(visible_symbols)} Exness symbols (5s intervals)...")
        # Scanner heartbeat metrics
        self.scan_count = 0
        self.last_scan_time = time.time()
        self.last_scan_duration = 0
        self.signals_before_scan = Signal.objects.count()
        from trading_engine.position_manager import PositionManager
        import threading
        pm = PositionManager()
        pm_thread = threading.Thread(target=pm.run_loop, daemon=True)
        pm_thread.start()
        self.stdout.write("Position Manager daemon started")
        last_tg_heartbeat = 0.0

        while True:
            try:
                # Auto-reconnect if MT5 drops
                # IPC-safe account_info with retry
                info = None
                for _retry_cnt in range(3):
                    try:
                        info = client.account_info()
                        if info is not None:
                            break
                    except Exception:
                        pass
                    import time as _retry_time
                    _retry_time.sleep(2)
                if info is None:
                    import time as _retry_time
                    _retry_time.sleep(5)
                    continue
                account.balance = Decimal(str(info["balance"]))
                account.equity = Decimal(str(info["equity"]))
                account.margin = Decimal(str(info["margin"]))
                account.save()

                # --- 4-Hour Telegram System Heartbeat (Every 14,400 seconds) ---
                # --- Scanner Heartbeat Push (Every cycle) ---
                if channel_layer and hasattr(self, 'scan_count') and self.scan_count % 5 == 0:
                    try:
                        async_to_sync(channel_layer.group_send)(
                            "trading",
                            {
                                "type": "event",
                                "payload": {
                                    "event": "SCANNER_HEARTBEAT",
                                    "scanner": {
                                        "scan_count": self.scan_count,
                                        "last_scan_time": datetime.fromtimestamp(self.last_scan_time, tz=timezone.utc).isoformat() if hasattr(self, 'last_scan_time') else "",
                                        "last_scan_duration_ms": self.last_scan_duration if hasattr(self, 'last_scan_duration') else 0,
                                        "symbols_tracked": len(visible_symbols),
                                        "status": "ACTIVE"
                                    }
                                }
                            }
                        )
                    except:
                        pass
                
                # --- Telegram 4-hour Heartbeat ---
                if tg_client and (time.time() - last_tg_heartbeat >= 14400.0 or last_tg_heartbeat == 0.0):
                    last_tg_heartbeat = time.time()
                    try:
                        eat_now_hb = EATPhaseEngine.get_eat_time()
                        subscribers = TelegramSubscriber.objects.filter(is_deleted=False, signal_alerts=True)
                        hb_msg = (
                            f"INSTITUTIONAL AI TRADING PLATFORM -- 4-HOUR SYSTEM HEARTBEAT\n\n"
                            f"Status: All 6 Enterprise NSSM Services Active & Operational\n"
                            f"Exness MT5 Terminal: Online (#{account.account_number} / {broker.server})\n\n"
                            f"Live Balance: ${float(account.balance):,.2f}\n"
                            f"Live Equity: ${float(account.equity):,.2f}\n"
                            f"Current EAT Time: `{eat_now_hb.strftime('%Y-%m-%d %H:%M:%S')} EAT (UTC+3)`\n\n"
                            f"Auto-Execution Gate: `Score >= 80/100` + `KOD Turtle Soup Limit Sniper`\n"
                            f"Risk & Phase Shield: `0.50 Lot Cap`, `4-Factor Spread/ATR Gate`, & `Adaptive Brain Quarantine` Active\n"
                            f"Next Heartbeat: In 4 hours (`{(eat_now_hb + timedelta(hours=4)).strftime('%H:%M:%S')} EAT`)"
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
                    # Safe upsert: delete duplicates first, then create
                    OpenPosition.objects.filter(account=account, broker_ticket=ticket).delete()
                    OpenPosition.objects.create(
                        account=account,
                        broker_ticket=ticket,
                        symbol=sym_obj,
                        direction=SignalDirection.BUY if pos.type == client.mt5.ORDER_TYPE_BUY else SignalDirection.SELL,
                        volume=Decimal(str(pos.volume)),
                        entry_price=Decimal(str(pos.price_open)),
                        current_price=Decimal(str(pos.price_current)),
                        stop_loss=Decimal(str(pos.sl)) if pos.sl else None,
                        take_profit=Decimal(str(pos.tp)) if pos.tp else None,
                        unrealized_profit=Decimal(str(pos.profit)),
                        opened_at=datetime.fromtimestamp(pos.time, tz=timezone.utc),
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
                                    outcome_icon = "TRADE HIT TAKE PROFIT (TP)" if is_win else "TRADE HIT STOP LOSS (SL)"
                                    out_msg = (
                                        f"{outcome_icon}\n\n"
                                        f"Asset: {deal.symbol} | Volume: {deal.volume} Lots\n"
                                        f"Closed P/L: **${deal.profit:,.2f} USD**\n\n"
                                        f"**AI Forensic Outcome Diagnosis**:\n"
                                        f"{ai_report['diagnosis']}\n\n"
                                        f"**Adaptive Brain Status**: Multiplier {ai_report['sizing_multiplier']}x | Quarantined: {ai_report['is_quarantined']}"
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
                                    s_icon = "SIGNAL HIT TAKE PROFIT (TP)" if hit_tp else "SIGNAL HIT STOP LOSS (SL)"
                                    s_msg = (
                                        f"{s_icon}\n\n"
                                        f"Asset: {active_sig.symbol.symbol} ({active_sig.strategy_name})\n"
                                        f"Target Entry: {active_sig.entry_price} -> Exit: {tick_sig.bid if active_sig.direction == 'BUY' else tick_sig.ask}\n\n"
                                        f"**AI Forensic Outcome Analysis**:\n"
                                        f"{ai_sig_report['diagnosis']}\n\n"
                                        f"**Adaptive Brain Action**: Multiplier adjusted to {ai_sig_report['sizing_multiplier']}x based on backtest expectancy."
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

                # ============================================================
                # SYMBOL / TIMEFRAME SCAN  (Modules 1-8)
                # ------------------------------------------------------------
                # Every iteration of this loop produces exactly one SignalTrace
                # and exactly one terminal outcome. The ``finally`` block is the
                # guarantee: no evaluation can leave this loop without being
                # recorded in the funnel and written to the LIFECYCLE log.
                # ============================================================
                _session_bucket = classify_session(datetime.now(timezone.utc))

                for symbol_obj in TradingSymbol.objects.filter(is_tradeable=True, is_deleted=False):
                    sym = symbol_obj.symbol
                    for mt5_tf, tf_enum in scan_timeframes:
                        trace = SignalTrace(symbol=sym, timeframe=tf_enum.value)
                        trace.mark(Stage.SCANNED)
                        try:
                            rates = client.mt5.copy_rates_from_pos(sym, mt5_tf, 0, 80)
                            if rates is None or len(rates) == 0:
                                trace.terminate(Outcome.NO_SETUP, Reason.NO_MT5_RATES,
                                                f"copy_rates_from_pos returned nothing for {tf_enum.value}")
                                continue
                            if len(rates) < 60:
                                trace.terminate(Outcome.NO_SETUP, Reason.INSUFFICIENT_HISTORY,
                                                f"only {len(rates)} bars returned")
                                continue

                            candles = []
                            for i, r in enumerate(rates):
                                candles.append(
                                    Candle(
                                        time=datetime.fromtimestamp(r["time"], tz=timezone.utc),
                                        open=Decimal(str(r["open"])),
                                        high=Decimal(str(r["high"])),
                                        low=Decimal(str(r["low"])),
                                        close=Decimal(str(r["close"])),
                                        volume=Decimal(str(r["tick_volume"])),
                                        completed=(i < len(rates) - 1),
                                    )
                                )

                            completed = [c for c in candles if c.completed]
                            if len(completed) < 60:
                                trace.terminate(Outcome.NO_SETUP, Reason.INSUFFICIENT_HISTORY,
                                                f"{len(completed)} completed bars < 60 required")
                                continue

                            from trading_engine.broker_intelligence import MT5BrokerIntelligence
                            broker_intel = MT5BrokerIntelligence(client.mt5)
                            spec = broker_intel.symbol_spec(sym)
                            if spec is None:
                                trace.terminate(Outcome.NO_SETUP, Reason.NO_SYMBOL_SPEC,
                                                "broker_intelligence returned no spec")
                                continue
                            trace.mark(Stage.DATA_OK, f"{len(completed)} completed bars",
                                       last_bar=completed[-1].time.isoformat())

                            # --- CRT range ---------------------------------------
                            crt_range = orchestrator.crt.detect(completed)
                            if crt_range is None:
                                trace.terminate(Outcome.NO_SETUP, Reason.NO_CRT_RANGE,
                                                f"lookback {CONFIG.crt.lookback} produced no range")
                                continue
                            trace.mark(Stage.CRT_CONFIRMED,
                                       f"{crt_range.state} range {crt_range.low}-{crt_range.high}",
                                       crt_state=crt_range.state)

                            # --- Liquidity sweep ---------------------------------
                            # detect_sweeps returns every candidate newest-first;
                            # select_sweep_for_displacement prefers one that already
                            # has its KOD displacement candle. See the docstring in
                            # trading_engine.liquidity for why this matters: 64.9%
                            # of live sweeps landed on the newest completed candle,
                            # where KOD is structurally unable to confirm.
                            sweep_candidates = orchestrator.liquidity.detect_sweeps(
                                completed, crt_range, spec.tick_size
                            )
                            sweep, sweep_note = select_sweep_for_displacement(
                                sweep_candidates, len(completed),
                                prefer_displaced=CONFIG.kod.scan_older_sweeps,
                            )
                            if sweep is None:
                                # CRT range without a liquidity sweep is not a
                                # Romeo TPT setup. The previous revision still
                                # wrote a Signal row for these (score 55, no
                                # Liquidity component), which is where 152 of the
                                # 460 rows in a six-hour window came from. They are
                                # always counted in the funnel; persisting them is
                                # now opt-in via PERSIST_NO_SWEEP_SIGNALS=1.
                                trace.terminate(Outcome.NO_SETUP, Reason.NO_LIQUIDITY_SWEEP,
                                                f"no pool swept in the last "
                                                f"{CONFIG.liquidity.lookback_candles} completed candles")
                                if CONFIG.pipeline.persist_no_sweep_signals:
                                    Signal.objects.update_or_create(
                                        symbol=symbol_obj,
                                        strategy_name=f"Romeo TPT ({tf_enum.value})",
                                        status="NO_SETUP",
                                        is_deleted=False,
                                        defaults=dict(
                                            author=admin_user,
                                            direction=SignalDirection.HOLD,
                                            entry_price=completed[-1].close,
                                            stop_loss=completed[-1].close,
                                            take_profit=completed[-1].close,
                                            confidence=Decimal("0"),
                                            rationale="CRT range present, no liquidity sweep detected",
                                            timeframe=tf_enum.value,
                                            lifecycle_stage=Stage.CRT_CONFIRMED.value,
                                            block_code=Reason.NO_LIQUIDITY_SWEEP.value,
                                            block_reason=trace.reason_text,
                                            lifecycle_json=json.dumps(trace.as_dict(), default=str)[:60000],
                                        ),
                                    )
                                continue
                            trace.mark(Stage.LIQUIDITY_FOUND, f"{sweep.kind} @ {sweep.swept_level} ({sweep_note})",
                                       sweep_kind=sweep.kind,
                                       sweep_level=sweep.swept_level,
                                       sweep_index=sweep.candle_index,
                                       rejection_ratio=sweep.rejection_ratio,
                                       candidates=len(sweep_candidates))
                            if sweep.failed:
                                trace.terminate(Outcome.NO_SETUP, Reason.SWEEP_INVALIDATED,
                                                sweep.description)
                                continue
                            trace.mark(Stage.SWEEP_VALID)

                            # --- Direction ---------------------------------------
                            # CRT + Turtle Soup fades the pool that was just taken,
                            # so the trade direction IS the sweep direction. The
                            # previous revision used ``structure.bias`` and fell
                            # back to BUY when structure was NEUTRAL, which
                            # disagreed with the sweep on 130 of 205 live sweeps
                            # (63.4%) and produced a 339:121 BUY:SELL skew. The
                            # canonical implementation in
                            # RomeoTPTOrchestrator.evaluate() has always used
                            # ``sweep.direction``; this path had drifted from it.
                            direction = sweep.direction
                            structure = orchestrator.structure.analyse(completed)
                            trace.fact(direction=direction.value,
                                       structure_bias=structure.bias.value,
                                       structure_event=structure.last_event)

                            atr = orchestrator._calculate_atr_14(completed)
                            trace.fact(atr=atr)

                            cisd = orchestrator.cisd.confirmed(completed, direction, structure)
                            session_state = orchestrator.session.evaluate(datetime.now(timezone.utc))
                            news_state = orchestrator.news.evaluate(datetime.now(timezone.utc), sym, [])

                            # --- Higher timeframe bias (Module 1) ----------------
                            htf_result = htf_engine.evaluate(sym, direction)
                            trace.fact(htf_status=htf_result.status.value,
                                       htf_biases=htf_result.summary)
                            if htf_result.aligned:
                                trace.mark(Stage.HTF_CONFIRMED, htf_result.detail)

                            # --- KOD ---------------------------------------------
                            kod_flag = orchestrator.kod.confirmed(completed, sweep, atr)
                            kod_subchecks = orchestrator.kod.subcheck_results(completed, sweep, atr)
                            if kod_subchecks is not None:
                                FUNNEL.note_kod_subchecks(kod_subchecks, session=_session_bucket)

                            score, htf_ok, risk_ok, volatility_ok = orchestrator.evaluate_signal(
                                direction, sweep, kod_flag, cisd, session_state, structure,
                                news_state, completed, spec, atr=atr, htf_result=htf_result,
                            )
                            kod_reason = getattr(orchestrator, "last_kod_reason", "n/a")
                            kod_ok = "KOD confirmed" in kod_reason
                            if kod_ok:
                                trace.mark(Stage.KOD_CONFIRMED, kod_reason)
                            fvg_mitigated = getattr(orchestrator, "last_fvg_mitigated", False)

                            trace.mark(
                                Stage.SCORE_CALCULATED,
                                score.gate_reason,
                                score=score.total,
                                tier=score.tier or "NONE",
                                kod=kod_ok,
                                kod_reason=kod_reason,
                                cisd=cisd,
                                fvg_ce_mitigated=fvg_mitigated,
                                session=session_state.name,
                                components={k: str(v) for k, v in score.components.items()},
                            )

                            confluences = [k for k, v in score.components.items() if v > 0]

                            # --- Spread measurement (needed for both paths) ------
                            mt5_spec = client.mt5.symbol_info(sym)
                            if not mt5_spec:
                                trace.terminate(Outcome.REJECTED, Reason.NO_SYMBOL_SPEC,
                                                "MT5 symbol_info returned None at scoring time")
                                continue
                            point = Decimal(str(mt5_spec.point if mt5_spec.point else "0.00001"))
                            raw_spread = Decimal(str(mt5_spec.spread if mt5_spec.spread else "5")) * point
                            pip_size = point * Decimal("10") if mt5_spec.digits in [3, 5] else point
                            spread_pips = (raw_spread / pip_size) if pip_size > 0 else Decimal("0")

                            # Stop: beyond the sweep extreme + (ATR multiple + spread buffer)
                            atr_buffer = CONFIG.risk.stop_atr_multiplier * atr + raw_spread
                            calc_sl = (
                                (min(completed[-1].low, crt_range.low) - atr_buffer)
                                if direction == Direction.BUY
                                else (max(completed[-1].high, crt_range.high) + atr_buffer)
                            )
                            calc_risk = abs(completed[-1].close - calc_sl)
                            spread_ratio = (raw_spread / calc_risk) if calc_risk > 0 else Decimal("0")
                            calc_tp = (
                                completed[-1].close + calc_risk * CONFIG.risk.take_profit_rr
                                if direction == Direction.BUY
                                else completed[-1].close - calc_risk * CONFIG.risk.take_profit_rr
                            )
                            trace.fact(spread_pips=spread_pips,
                                       spread_risk_ratio=spread_ratio,
                                       entry=completed[-1].close,
                                       stop_loss=calc_sl,
                                       take_profit=calc_tp,
                                       risk_distance=calc_risk)

                            # Absolute pip cap (disabled by default, see strategy_config)
                            if CONFIG.spread.max_pips is not None and spread_pips > CONFIG.spread.max_pips:
                                trace.terminate(
                                    Outcome.REJECTED, Reason.SPREAD_ABSOLUTE_CAP,
                                    f"{spread_pips:.2f} pips > {CONFIG.spread.max_pips} pip cap")
                                continue

                            if calc_risk > 0 and spread_ratio > CONFIG.spread.max_risk_ratio:
                                trace.terminate(
                                    Outcome.REJECTED, Reason.SPREAD_RISK_RATIO,
                                    f"spread {float(spread_ratio) * 100:.2f}% of the "
                                    f"{float(calc_risk):.6f} risk distance exceeds the "
                                    f"{float(CONFIG.spread.max_risk_ratio) * 100:.0f}% limit "
                                    f"({float(spread_pips):.2f} pips)")
                                continue

                            if score.passed:
                                trace.mark(Stage.TIER_QUALIFIED, score.gate_reason)

                            # --- Persist / refresh the Signal row -----------------
                            if score.total < CONFIG.pipeline.min_persist_score:
                                trace.terminate(Outcome.WATCHLIST, Reason.BELOW_TIER_1,
                                                f"score {score.total} below the "
                                                f"{CONFIG.pipeline.min_persist_score} persistence floor")
                                continue

                            is_high_conf = bool(score.passed)
                            sig, created = upsert_signal(
                                symbol_obj=symbol_obj,
                                tf_value=tf_enum.value,
                                direction=direction,
                                status="ACTIVE" if is_high_conf else "WATCHLIST",
                                entry=completed[-1].close,
                                stop_loss=calc_sl,
                                take_profit=calc_tp,
                                score=score,
                                trace=trace,
                                htf_result=htf_result,
                                spread_pips=spread_pips,
                                spread_ratio=spread_ratio,
                                confluences=confluences,
                                block_code="" if is_high_conf else (score.gate_code or "TIER_NOT_QUALIFIED"),
                                block_reason="" if is_high_conf else score.gate_reason,
                            )
                            trace.signal_id = sig.id
                            trace.mark(Stage.SIGNAL_PERSISTED,
                                       "created" if created else "refreshed in place")

                            self.stdout.write(
                                f"{'NEW' if created else 'UPDATED'} SIGNAL: {sym} ({tf_enum.value}) "
                                f"{sig.direction} score={score.total} tier={score.tier or 'NONE'} "
                                f"htf={htf_result.status.value}"
                            )
                            broadcast_signal(sig, sym, score, htf_result, spread_pips, created)

                            # Telegram routing for qualified, high-conviction setups
                            if tg_client and is_high_conf:
                                maybe_telegram_signal(sig, sym, tf_enum, symbol_obj)

                            if not is_high_conf:
                                # This is the Phase 3 answer: an exact, specific
                                # reason for every signal that stays on the
                                # watchlist, derived from the scoring gate rather
                                # than guessed from prose.
                                trace.terminate(Outcome.WATCHLIST,
                                                score.gate_code or Reason.TIER_NOT_QUALIFIED.value,
                                                score.gate_reason)
                                continue

                            # ==========================================================
                            # EXECUTION PATH
                            # ==========================================================
                            if not broker_setting.enable_autotrading:
                                mark_signal_blocked(sig, Reason.AUTOTRADING_DISABLED.value,
                                                    "BrokerSetting.enable_autotrading is False")
                                trace.terminate(Outcome.REJECTED, Reason.AUTOTRADING_DISABLED)
                                continue

                            # --- Execution cooldown -------------------------------
                            # Keyed on *executed* trades only. The previous revision
                            # keyed a 30-minute window on ANY signal row for the same
                            # symbol/direction/timeframe -- including the WATCHLIST
                            # rows this very loop creates -- and, when it hit, did a
                            # bare ``continue`` with no log line at all. Because a
                            # WATCHLIST row exists for almost every symbol at almost
                            # all times, that test silently suppressed the qualifying
                            # signal that arrived later in the same window. It is the
                            # single largest reason the platform showed hundreds of
                            # watchlist entries and zero active trades.
                            cooldown_cut = django_tz.now() - timedelta(
                                minutes=CONFIG.pipeline.execution_cooldown_minutes)
                            recent_execution = (
                                Order.objects.filter(
                                    account=account, symbol=symbol_obj,
                                    direction=sig.direction, created_at__gte=cooldown_cut,
                                ).exists()
                                or Signal.objects.filter(
                                    symbol=symbol_obj, direction=sig.direction,
                                    status__in=("EXECUTED", "SHADOW_WOULD_EXECUTE"),
                                    created_at__gte=cooldown_cut, is_deleted=False,
                                ).exclude(id=sig.id).exists()
                            )
                            if recent_execution:
                                mark_signal_blocked(
                                    sig, Reason.EXECUTION_COOLDOWN.value,
                                    f"an order for {sym} {sig.direction} was already sent within the "
                                    f"last {CONFIG.pipeline.execution_cooldown_minutes} minutes")
                                trace.terminate(Outcome.REJECTED, Reason.EXECUTION_COOLDOWN,
                                                f"{CONFIG.pipeline.execution_cooldown_minutes}-minute window")
                                continue

                            eat_status = EATPhaseEngine.evaluate_asset_phase(sym, score.total)
                            if not eat_status.is_allowed:
                                mark_signal_blocked(sig, Reason.EAT_PHASE_BLOCK.value, eat_status.reason)
                                trace.terminate(Outcome.REJECTED, Reason.EAT_PHASE_BLOCK, eat_status.reason)
                                continue

                            is_news_blocked, news_reason = news_engine.is_news_blackout_active(
                                sym, datetime.now(timezone.utc))
                            if is_news_blocked:
                                mark_signal_blocked(sig, Reason.NEWS_BLACKOUT.value, news_reason)
                                trace.terminate(Outcome.REJECTED, Reason.NEWS_BLACKOUT, news_reason)
                                continue

                            brain_passed, brain_msg, brain_mult = adaptive_brain.evaluate(sym, score.total)
                            if not brain_passed:
                                mark_signal_blocked(sig, Reason.ADAPTIVE_BRAIN_BLOCK.value, brain_msg)
                                trace.terminate(Outcome.REJECTED, Reason.ADAPTIVE_BRAIN_BLOCK, brain_msg)
                                continue

                            mgr = AccountManager(account, client)
                            eval_result = mgr.evaluate_status()
                            if not eval_result.trading_allowed:
                                mark_signal_blocked(sig, Reason.RISK_CAP_REACHED.value, eval_result.reason)
                                trace.terminate(Outcome.REJECTED, Reason.RISK_CAP_REACHED, eval_result.reason)
                                continue

                            if OpenPosition.objects.filter(
                                account=account, symbol=symbol_obj, is_deleted=False
                            ).exists():
                                mark_signal_blocked(
                                    sig, Reason.DUPLICATE_OPEN_POSITION.value,
                                    f"a position on {sym} is already open on account "
                                    f"{account.account_number}")
                                trace.terminate(Outcome.REJECTED, Reason.DUPLICATE_OPEN_POSITION)
                                continue

                            trace.mark(Stage.RISK_APPROVED,
                                       f"{eval_result.mode.value}: {eval_result.reason}",
                                       account_mode=eval_result.mode.value,
                                       open_positions=eval_result.active_open_positions,
                                       today_trades=eval_result.today_trades_count)

                            passed_gate, gate_msg, gate_meta = TradeExecutionGate.evaluate(
                                client, symbol_obj, sig, score.components, completed, crt_range
                            )
                            gate_code = str(gate_meta.get("code") or Reason.RISK_CAP_REACHED.value)
                            trace.fact(gate_code=gate_code,
                                       gate_adx=gate_meta.get("adx"),
                                       gate_rsi=gate_meta.get("rsi"),
                                       gate_atr_ratio=gate_meta.get("atr_ratio"))
                            if not passed_gate:
                                # The rejection code comes from the gate itself.
                                # Substring-matching the English message is what
                                # previously recorded every RSI/ADX/volatility
                                # rejection as "BLOCKED_RISK_CAP_REACHED".
                                mark_signal_blocked(sig, gate_code, gate_msg)
                                trace.terminate(Outcome.REJECTED, gate_code, gate_msg)
                                continue
                            trace.mark(Stage.EXECUTION_GATE_PASSED, gate_msg)

                            mt5_tick = client.mt5.symbol_info_tick(sym)
                            mt5_spec = client.mt5.symbol_info(sym)
                            if not mt5_tick or not mt5_spec:
                                mark_signal_blocked(sig, Reason.GATE_MISSING_TICK.value,
                                                    "no live tick or symbol spec at execution time")
                                trace.terminate(Outcome.REJECTED, Reason.GATE_MISSING_TICK)
                                continue
                            if mt5_tick.bid <= 0 or mt5_tick.ask <= 0 or getattr(mt5_spec, "trade_mode", 1) == 0:
                                mark_signal_blocked(
                                    sig, Reason.MARKET_CLOSED.value,
                                    f"bid={mt5_tick.bid} ask={mt5_tick.ask} "
                                    f"trade_mode={getattr(mt5_spec, 'trade_mode', 1)}")
                                trace.terminate(Outcome.REJECTED, Reason.MARKET_CLOSED)
                                continue

                            # --- Position sizing ----------------------------------
                            lot_size = mgr.calculate_position_size(
                                symbol_obj, sig.entry_price, sig.stop_loss, sig.confidence)

                            point = Decimal(str(mt5_spec.point if mt5_spec.point else "0.00001"))
                            digits = int(mt5_spec.digits if mt5_spec.digits else symbol_obj.digits)
                            stops_level = int(getattr(mt5_spec, "trade_stops_level", 15) or 15)
                            min_stop_dist = point * Decimal(
                                str(max(stops_level, 15) + getattr(mt5_spec, "spread", 5) + 10))
                            lot_step = Decimal(str(mt5_spec.volume_step if mt5_spec.volume_step else "0.01"))
                            min_lot = Decimal(str(mt5_spec.volume_min if mt5_spec.volume_min else "0.01"))
                            max_lot = Decimal(str(mt5_spec.volume_max if mt5_spec.volume_max else "100"))

                            if eat_status.sizing_multiplier < Decimal("1.0") and eat_status.sizing_multiplier > Decimal("0.0"):
                                lot_size = max(min_lot, (lot_size * eat_status.sizing_multiplier / lot_step)
                                               .to_integral_value(rounding=ROUND_DOWN) * lot_step)

                            _risk_mult = tier_risk_multiplier(getattr(score, "tier", ""))
                            if _risk_mult != Decimal("1.0") and _risk_mult > 0:
                                _scaled = (lot_size * _risk_mult / lot_step).to_integral_value(
                                    rounding=ROUND_DOWN) * lot_step
                                lot_size = max(min_lot, min(_scaled, max_lot))

                            if lot_size <= 0:
                                mark_signal_blocked(sig, Reason.INVALID_LOT_SIZE.value,
                                                    f"sizing produced {lot_size} lots")
                                trace.terminate(Outcome.REJECTED, Reason.INVALID_LOT_SIZE)
                                continue

                            risk_pct = (
                                (abs(sig.entry_price - sig.stop_loss)
                                 * lot_size
                                 * Decimal(str(getattr(mt5_spec, "trade_contract_size", 100000) or 100000))
                                 / account.balance * Decimal("100"))
                                if account.balance > 0 else Decimal("0")
                            )
                            trace.mark(Stage.SIZED,
                                       f"{lot_size} lots (tier x{_risk_mult}, EAT x{eat_status.sizing_multiplier})",
                                       lots=lot_size, risk_multiplier=_risk_mult,
                                       risk_pct=risk_pct)

                            # --- Module 4: three-way entry selection ---------------
                            _exec_tier = getattr(score, "tier", "") or "TIER_1"
                            pips_retracement = point * Decimal("18") if digits in [3, 5] else point * Decimal("2")
                            _ref = Decimal(str(mt5_tick.ask if sig.direction == "BUY" else mt5_tick.bid))

                            _ce_price = None
                            _ce_note = ""
                            if _exec_tier == "TIER_2":
                                try:
                                    _aligned = [
                                        g for g in orchestrator.fvg.detect(completed)
                                        if g.direction == direction and g.state in {"VALID", "MITIGATED"}
                                    ]
                                    if _aligned:
                                        _ce = (_aligned[-1].low + _aligned[-1].high) / Decimal("2")
                                        _ok_side = _ce < _ref if sig.direction == "BUY" else _ce > _ref
                                        _distance = abs(_ref - _ce)
                                        _max_distance = pips_retracement * Decimal("12")
                                        if not _ok_side:
                                            _ce_note = (
                                                f"price has already traded through the FVG CE "
                                                f"({_ce} vs market {_ref})")
                                        elif _distance > _max_distance:
                                            _ce_note = (
                                                f"FVG CE {_ce} is {float(_distance / pip_size):.1f} pips "
                                                f"away, beyond the "
                                                f"{float(_max_distance / pip_size):.1f} pip limit")
                                        else:
                                            _ce_price = _ce
                                    else:
                                        _ce_note = "no aligned VALID/MITIGATED fair value gap"
                                except Exception as _ce_err:
                                    logger.warning("FVG CE calculation failed for %s: %s", sym, _ce_err)
                                    _ce_note = f"CE computation failed: {_ce_err}"

                            if _exec_tier in ("TIER_1", "TIER_3"):
                                _order_type = "MARKET"
                                _entry_label = "MARKET on KOD close"
                                exec_price = round(_ref, digits)
                            else:
                                _order_type = "LIMIT"
                                if _ce_price is not None:
                                    _entry_label = "LIMIT at FVG 50% CE"
                                    exec_price = round(_ce_price, digits)
                                else:
                                    _entry_label = "LIMIT sniper retracement"
                                    exec_price = round(
                                        (Decimal(str(mt5_tick.ask)) - pips_retracement) if sig.direction == "BUY"
                                        else (Decimal(str(mt5_tick.bid)) + pips_retracement), digits)

                            if sig.direction == "BUY":
                                exec_sl = round(min(sig.stop_loss, exec_price - min_stop_dist), digits)
                                exec_tp = round(max(sig.take_profit, exec_price + min_stop_dist * Decimal("2")), digits)
                            else:
                                exec_sl = round(max(sig.stop_loss, exec_price + min_stop_dist), digits)
                                exec_tp = round(min(sig.take_profit, exec_price - min_stop_dist * Decimal("2")), digits)

                            exp_ts = None
                            if _order_type == "LIMIT":
                                exp_ts = int((datetime.now(timezone.utc) + timedelta(minutes=4)).timestamp())
                                if eat_status.expiration_clamp_utc is not None:
                                    exp_ts = min(exp_ts, eat_status.expiration_clamp_utc)

                            trace.fact(order_type=_order_type, entry_label=_entry_label,
                                       exec_price=exec_price, exec_sl=exec_sl, exec_tp=exec_tp,
                                       ce_note=_ce_note or "-")

                            # Module 7: one line carrying every fact required to
                            # reconstruct the decision after the fact.
                            logger.info(
                                "TRADE-DECISION %s %s | %s %s | tier=%s score=%s | conf=%s | "
                                "entry=%s sl=%s tp=%s | lots=%s risk=%.3f%% | "
                                "spread=%.2fpips ratio=%.2f%% | htf=%s (%s) | gate=%s | %s",
                                sym, tf_enum.value, sig.direction, _entry_label,
                                _exec_tier, score.total, ",".join(confluences),
                                exec_price, exec_sl, exec_tp, lot_size, float(risk_pct),
                                float(spread_pips), float(spread_ratio) * 100,
                                htf_result.status.value, htf_result.summary, gate_msg,
                                "SHADOW" if SHADOW_MODE else "LIVE",
                            )
                            self.stdout.write(
                                f"EXECUTING {_exec_tier} [{sym} {tf_enum.value}]: {_entry_label}, "
                                f"Mode={eval_result.mode.value}, Phase={eat_status.phase_name}, "
                                f"Lots={lot_size}, {sig.direction}, Entry={exec_price}, "
                                f"SL={exec_sl}, TP={exec_tp}"
                            )

                            req = BrokerOrderRequest(
                                symbol=sym,
                                direction=sig.direction,
                                volume=lot_size,
                                price=exec_price,
                                stop_loss=exec_sl,
                                take_profit=exec_tp,
                                deviation=broker_setting.order_deviation_points,
                                order_type=_order_type,
                                expiration=exp_ts,
                                is_pit_open=eat_status.is_pit_open,
                            )

                            if SHADOW_MODE:
                                logger.info(
                                    "SHADOW-TRADE %s %s | %s | %s | lots=%s risk_mult=%s | "
                                    "entry=%s sl=%s tp=%s | score=%s tier=%s | spread=%.2f pips | "
                                    "htf=%s | gate=%s | WOULD SEND (no order transmitted)",
                                    sym, tf_enum.value, sig.direction, _entry_label,
                                    lot_size, _risk_mult, exec_price, exec_sl, exec_tp,
                                    score.total, _exec_tier, float(spread_pips),
                                    htf_result.summary, gate_msg,
                                )
                                self.stdout.write(
                                    f"SHADOW-TRADE [{sym} {tf_enum.value}] {sig.direction} "
                                    f"{_exec_tier} {_entry_label}: {lot_size} lots @ {exec_price} "
                                    f"SL={exec_sl} TP={exec_tp} (score {score.total}) "
                                    f"-- suppressed, SHADOW_MODE=1"
                                )
                                Signal.objects.filter(id=sig.id).update(
                                    status="SHADOW_WOULD_EXECUTE",
                                    lifecycle_stage=Stage.SIZED.value,
                                    block_code=Reason.SHADOW_MODE.value,
                                    block_reason=describe(Reason.SHADOW_MODE.value,
                                                          f"{_exec_tier} {_entry_label} "
                                                          f"{lot_size} lots @ {exec_price}"),
                                    position_size=lot_size,
                                    risk_pct=risk_pct,
                                )
                                trace.terminate(Outcome.SHADOW, Reason.SHADOW_MODE,
                                                f"{_exec_tier} {_order_type} {lot_size} lots @ {exec_price}")
                                continue

                            _send_started = time.perf_counter()
                            order_res = client.place_order(req)
                            _send_ms = (time.perf_counter() - _send_started) * 1000.0
                            trace.mark(Stage.ORDER_SENT,
                                       f"{_order_type} {lot_size} @ {exec_price}",
                                       order_latency_ms=round(_send_ms, 1),
                                       retcode=order_res.get("retcode"),
                                       attempts=order_res.get("attempts"))
                            logger.info(
                                "BROKER-RESPONSE %s | retcode=%s comment=%s order=%s deal=%s "
                                "attempts=%s latency=%.0fms",
                                sym, order_res.get("retcode"), order_res.get("comment"),
                                order_res.get("order"), order_res.get("deal"),
                                order_res.get("attempts"), _send_ms,
                            )

                            if order_res.get("retcode") not in (10008, 10009, 10010):
                                mark_signal_blocked(
                                    sig, Reason.ORDER_REJECTED.value,
                                    f"retcode={order_res.get('retcode')} "
                                    f"comment={order_res.get('comment')}")
                                trace.terminate(
                                    Outcome.REJECTED, Reason.ORDER_REJECTED,
                                    f"retcode={order_res.get('retcode')} "
                                    f"comment={order_res.get('comment')}")
                                self.stdout.write(
                                    f"MT5 Order execution failed [{sym}]: "
                                    f"retcode={order_res.get('retcode')}, "
                                    f"comment={order_res.get('comment')}")
                                continue

                            ticket_str = str(order_res.get("deal") or order_res.get("order") or "")
                            filled_price = Decimal(str(order_res.get("price") or exec_price))
                            is_pending = order_res.get("retcode") == 10008

                            Order.objects.create(
                                account=account,
                                signal=sig,
                                symbol=symbol_obj,
                                direction=sig.direction,
                                order_type=_order_type,
                                status="PENDING" if is_pending else "FILLED",
                                requested_volume=lot_size,
                                filled_volume=Decimal("0") if is_pending else lot_size,
                                requested_price=exec_price,
                                filled_price=None if is_pending else filled_price,
                                stop_loss=exec_sl,
                                take_profit=exec_tp,
                                broker_ticket=ticket_str,
                            )

                            if is_pending:
                                # A resting limit is not a position yet. Phase 3's
                                # "limit entry not yet reached" case.
                                Signal.objects.filter(id=sig.id).update(
                                    status="WAITING_ENTRY",
                                    lifecycle_stage=Stage.ORDER_SENT.value,
                                    block_code=Reason.LIMIT_NOT_REACHED.value,
                                    block_reason=describe(
                                        Reason.LIMIT_NOT_REACHED.value,
                                        f"pending {_order_type} #{ticket_str} resting at {exec_price}, "
                                        f"market {_ref}"),
                                    position_size=lot_size,
                                    risk_pct=risk_pct,
                                )
                                trace.terminate(Outcome.WAITING_FOR_RETRACEMENT, Reason.LIMIT_NOT_REACHED,
                                                f"pending order #{ticket_str} at {exec_price}")
                                self.stdout.write(
                                    f"PENDING ORDER PLACED: {sym} {sig.direction} @ {exec_price} "
                                    f"(Ticket: #{ticket_str})")
                                continue

                            OpenPosition.objects.filter(account=account, broker_ticket=ticket_str).delete()
                            OpenPosition.objects.create(
                                account=account,
                                broker_ticket=ticket_str,
                                symbol=symbol_obj,
                                direction=SignalDirection.BUY if sig.direction == "BUY" else SignalDirection.SELL,
                                volume=lot_size,
                                entry_price=filled_price,
                                current_price=filled_price,
                                stop_loss=exec_sl,
                                take_profit=exec_tp,
                                unrealized_profit=Decimal("0.00"),
                                opened_at=django_tz.now(),
                            )
                            Signal.objects.filter(id=sig.id).update(
                                status="EXECUTED",
                                lifecycle_stage=Stage.FILLED.value,
                                block_code="",
                                block_reason="",
                                position_size=lot_size,
                                risk_pct=risk_pct,
                            )
                            trace.mark(Stage.FILLED, f"ticket #{ticket_str} @ {filled_price}",
                                       ticket=ticket_str, fill_price=filled_price)
                            trace.terminate(Outcome.ACTIVE, Reason.ORDER_FILLED,
                                            f"ticket #{ticket_str} at {filled_price}")
                            self.stdout.write(
                                f"TRADE EXECUTED & RECORDED: {sym} {sig.direction} @ {filled_price} "
                                f"(Ticket: #{ticket_str})")

                            if tg_client:
                                notify_execution(sig, sym, tf_enum, eval_result, lot_size,
                                                 filled_price, exec_sl, exec_tp, gate_msg, ticket_str)

                        except Exception as eval_err:
                            logger.exception("Strategy evaluation error [%s %s]: %s",
                                             sym, tf_enum.value, eval_err)
                            self.stderr.write(f"Strategy evaluation error [{sym} {tf_enum.value}]: {eval_err}")
                            if not trace.terminated:
                                trace.terminate(Outcome.ERROR, Reason.EVALUATION_ERROR, str(eval_err))
                        finally:
                            # Phase 2 guarantee: no signal disappears silently.
                            if not trace.terminated:
                                trace.terminate(
                                    Outcome.ERROR, Reason.EVALUATION_ERROR,
                                    "evaluation ended without an explicit terminal decision")
                            FUNNEL.record(trace, session=_session_bucket)
                            if CONFIG.pipeline.trace_all_evaluations or trace.outcome != Outcome.NO_SETUP.value:
                                trace.log()

                # --- Funnel reporting (Module 4) ----------------------------
                _cycle_no = FUNNEL.cycle_complete()
                if _cycle_no % max(1, CONFIG.pipeline.funnel_report_every_cycles) == 0:
                    publish_funnel(_cycle_no)

                time.sleep(1)
            except KeyboardInterrupt:
                self.stdout.write("MT5 Engine loop stopping...")
                break
            except Exception as e:
                self.stderr.write(f"Error inside MT5 engine loop: {e}")
                try: client.is_connected = False
                except: pass
                time.sleep(1)

