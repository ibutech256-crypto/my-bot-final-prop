import os, sys, signal, pathlib, shutil, time

os.chdir(r"C:\prop-frim-bot")
signal.signal(signal.SIGINT, signal.SIG_IGN)

# ===== 1. WRITE CORRECT SCORING ENGINE v2.2 =====
scoring = '''
"""v2.2 Scoring Engine - Properly weight KOD, cap non-KOD scores."""
from __future__ import annotations
from decimal import Decimal
from trading_engine.types import Direction, LiquidityEvent, NewsState, ScoreBreakdown, SessionState, StructureState

class ScoringEngine:
    weights = {
        "CRT": Decimal("12"),
        "Liquidity": Decimal("15"),
        "KOD": Decimal("18"),
        "CISD": Decimal("12"),
        "HTF Alignment": Decimal("15"),
        "Session": Decimal("8"),
        "Structure": Decimal("10"),
        "Risk": Decimal("5"),
        "Volatility": Decimal("3"),
        "News": Decimal("2"),
    }

    def score(self, direction, liquidity, kod, cisd, htf, session, structure, risk_ok, volatility_ok, news, minimum=Decimal("75")):
        c = {
            "CRT": self.weights["CRT"],
            "Liquidity": self.weights["Liquidity"] if liquidity and not liquidity.failed else Decimal("0"),
            "KOD": self.weights["KOD"] if kod else Decimal("0"),
            "CISD": self.weights["CISD"] if cisd else Decimal("0"),
            "HTF Alignment": self.weights["HTF Alignment"] if htf else Decimal("0"),
            "Session": self.weights["Session"] if session.liquid else Decimal("0"),
            "Structure": self.weights["Structure"] if structure.bias in {direction, Direction.NEUTRAL} else Decimal("0"),
            "Risk": self.weights["Risk"] if risk_ok else Decimal("0"),
            "Volatility": self.weights["Volatility"] if volatility_ok else Decimal("0"),
            "News": self.weights["News"] if news.trading_allowed else Decimal("0"),
        }
        total = sum(c.values(), Decimal("0"))
        if not kod:
            total = min(total, Decimal("70"))
        passed = False
        if total >= Decimal("55") and liquidity and not liquidity.failed and kod:
            passed = True
        if total >= Decimal("70") and htf and kod:
            passed = True
        if total >= minimum and kod:
            passed = True
        return ScoreBreakdown(total, c, passed)
'''
open(r"C:\prop-frim-bot\trading_engine\scoring.py", "w").write(scoring)
print("1. SCORING v2.2 WRITTEN")

# ===== 2. READ AND FIX ENGINE FILE =====
engine_path = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
engine = open(engine_path, "r").read()
changes = 0

# Fix A: Add signal handler
if "SIG_IGN" not in engine:
    old = "from telegram.bot import TelegramBotClient"
    new = old + "\nimport signal, os\ntry:\n    signal.signal(signal.SIGINT, signal.SIG_IGN)\nexcept:\n    pass\n"
    engine = engine.replace(old, new, 1)
    changes += 1
    print("2A. Signal handler added")

# Fix B: Dedup
old = 'recent = Signal.objects.filter(symbol=symbol_obj, direction=direction.value, strategy_name=f"Romeo TPT ({tf_enum.value})", created_at__gte=django_tz.now() - django_tz.timedelta(minutes=2)).exists()\n                                        if not recent:'
new = 'recent = Signal.objects.filter(symbol=symbol_obj, direction=direction.value, strategy_name=f"Romeo TPT ({tf_enum.value})", status__in=["ACTIVE","ACTIVE_MONITORING","EXECUTION_READY","EXECUTING","EXECUTED","PROTECTED"], created_at__gte=django_tz.now() - django_tz.timedelta(hours=4)).exists()\n                                        if not recent:'
if old in engine:
    engine = engine.replace(old, new)
    changes += 1
    print("2B. Dedup window extended")
else:
    print("2B. Dedup: pattern not found")

# Fix C: Status
old = 'status="ACTIVE" if is_high_conf else "WATCHLIST",'
if old in engine:
    engine = engine.replace(old, 'status=lifecycle_status,')
    changes += 1
    print("2C. Status -> lifecycle_status")
else:
    # Try alternate pattern
    old2 = 'status="ACTIVE" if is_high_conf or score.total >= Decimal("55") else "WATCHLIST",'
    if old2 in engine:
        engine = engine.replace(old2, 'status=lifecycle_status,')
        changes += 1
        print("2C. Status -> lifecycle_status (alt)")
    else:
        print("2C. Status: pattern not found")

# Fix D: Lifecycle before Signal.create()
old = '\n                                        sig = Signal.objects.create('
new = '\n                                        # v2.2: Lifecycle states\n                                        lifecycle_status = "WATCHLIST"\n                                        if score.total >= Decimal("85"):\n                                            lifecycle_status = "EXECUTION_READY"\n                                        elif score.total >= Decimal("70"):\n                                            lifecycle_status = "EXECUTION_READY"\n                                        elif score.total >= Decimal("55"):\n                                            lifecycle_status = "ACTIVE_MONITORING"\n                                        else:\n                                            lifecycle_status = "WATCHLIST"\n                                        sig = Signal.objects.create('
if old in engine:
    engine = engine.replace(old, new, 1)
    changes += 1
    print("2D. Lifecycle block added")
else:
    print("2D. Create pattern not found")

# Fix E: Telegram flood - only send for audited deals
old = 'if tg_client:\n                                    subscribers = TelegramSubscriber.objects.filter(is_deleted=False, signal_alerts=True)\n                                    outcome_icon = "TRADE HIT TAKE PROFIT (TP)" if is_win else "TRADE HIT STOP LOSS (SL)"'
new = 'if tg_client and deal_audited:\n                                    subscribers = TelegramSubscriber.objects.filter(is_deleted=False, signal_alerts=True)\n                                    outcome_icon = "TRADE HIT TAKE PROFIT (TP)" if is_win else "TRADE HIT STOP LOSS (SL)"'
if old in engine:
    engine = engine.replace(old, new)
    changes += 1
    print("2E. Telegram flood fixed")
else:
    print("2E. TG pattern not found")

if changes > 0:
    open(engine_path, "w").write(engine)
    print(f"Engine updated ({changes} fixes)")
else:
    print("No changes needed")

# ===== 3. CLEAR ALL PYCACHE =====
for p in pathlib.Path(r"C:\prop-frim-bot").rglob("__pycache__"):
    try: shutil.rmtree(p)
    except: pass
print("3. All pycache cleared")

# ===== 4. VERIFY SYNTAX =====
import py_compile
try:
    py_compile.compile(engine_path, doraise=True)
    print("4. ENGINE SYNTAX OK")
except Exception as e:
    print(f"4. ENGINE SYNTAX ERROR: {e}")

try:
    py_compile.compile(r"C:\prop-frim-bot\trading_engine\scoring.py", doraise=True)
    print("4. SCORING SYNTAX OK")
except Exception as e:
    print(f"4. SCORING SYNTAX ERROR: {e}")

# ===== 5. CONFIGURE NSSM =====
os.system('nssm set TradingMT5Engine AppStopMethodOverride 0')
os.system('nssm set TradingMT5Engine AppThrottle 3000')
os.system('nssm set TradingMT5Engine Application C:\\Windows\\System32\\cmd.exe')
os.system('nssm set TradingMT5Engine AppParameters /c C:\\prop-frim-bot\\run_engine.bat')
os.system('nssm set TradingMT5Engine AppDirectory C:\\prop-frim-bot')
print("5. NSSM configured")

# ===== 6. RESTART ENGINE =====
os.system('nssm stop TradingMT5Engine')
time.sleep(3)
os.system('nssm start TradingMT5Engine')
time.sleep(5)

# ===== 7. CHECK =====
r = os.popen('nssm status TradingMT5Engine').read().strip()
print(f"6. ENGINE: {r}")
r = os.popen('powershell -Command "(Get-Process python -ErrorAction SilentlyContinue).Count"').read().strip()
print(f"7. PYTHON: {r}")
r = os.popen('powershell -Command "Get-Content C:\\prop-frim-bot\\logs\\TradingMT5Engine.log -Tail 5"').read()
print(f"8. LOG:\n{r}")

print("\nDONE!")
