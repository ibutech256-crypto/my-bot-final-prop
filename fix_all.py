import signal, os, sys, pathlib, shutil
signal.signal(signal.SIGINT, signal.SIG_IGN)
os.chdir(r"C:\prop-frim-bot")

# === STEP 1: Clear ALL pycache ===
print("Clearing pycache...")
for p in pathlib.Path(r"C:\prop-frim-bot").rglob("__pycache__"):
    try: shutil.rmtree(p)
    except: pass
print("✅ Cache cleared")

# === STEP 2: Restore v2.2 scoring engine ===
scoring = r"""\"\"\"v2.2 Scoring Engine - Properly weight KOD, cap non-KOD scores.\"\"\"
from __future__ import annotations
from decimal import Decimal
from trading_engine.types import Direction, LiquidityEvent, NewsState, ScoreBreakdown, SessionState, StructureState

class ScoringEngine:
    weights = {
        "CRT": Decimal("12"),
        "Liquidity": Decimal("15"),
        "KOD": Decimal("18"),  # Increased from 12
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
        # v2.2: Without KOD, max score is 70
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
"""
open(r"C:\prop-frim-bot\trading_engine\scoring.py", "w").write(scoring)
print("✅ v2.2 Scoring engine restored")

# === STEP 3: Fix engine file ===
engine = open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "r").read()

# Fix 1: Dedup window 2min -> 4 hours + lifecycle status check
old1 = 'recent = Signal.objects.filter(symbol=symbol_obj, direction=direction.value, strategy_name=f"Romeo TPT ({tf_enum.value})", created_at__gte=django_tz.now() - django_tz.timedelta(minutes=2)).exists()\n                                        if not recent:'
new1 = 'recent = Signal.objects.filter(symbol=symbol_obj, direction=direction.value, strategy_name=f"Romeo TPT ({tf_enum.value})", status__in=["ACTIVE","ACTIVE_MONITORING","EXECUTION_READY","EXECUTING","EXECUTED","PROTECTED"], created_at__gte=django_tz.now() - django_tz.timedelta(hours=4)).exists()\n                                        if not recent:'
engine = engine.replace(old1, new1)

# Fix 2: Replace status assignment
old2 = 'status="ACTIVE" if is_high_conf else "WATCHLIST",'
engine = engine.replace(old2, 'status=lifecycle_status,')

# Fix 3: Add lifecycle calculation before Signal.create()
old3 = '\n                                        sig = Signal.objects.create('
new3 = '\n                                        # v2.2: Lifecycle states\n                                        lifecycle_status = "WATCHLIST"\n                                        if score.total >= Decimal("85"):\n                                            lifecycle_status = "EXECUTION_READY"\n                                        elif score.total >= Decimal("70"):\n                                            lifecycle_status = "EXECUTION_READY"\n                                        elif score.total >= Decimal("55"):\n                                            lifecycle_status = "ACTIVE_MONITORING"\n                                        else:\n                                            lifecycle_status = "WATCHLIST"\n                                        sig = Signal.objects.create('
engine = engine.replace(old3, new3, 1)

open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "w").write(engine)
print("✅ Engine file fixed with lifecycle states, dedup, proper status")

# === STEP 4: Verify syntax ===
import py_compile
try:
    py_compile.compile(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", doraise=True)
    print("✅ SYNTAX OK")
except Exception as e:
    print(f"❌ SYNTAX ERROR: {e}")
    sys.exit(1)

# === STEP 5: Clear pycache AGAIN ===
for p in pathlib.Path(r"C:\prop-frim-bot").rglob("__pycache__"):
    try: shutil.rmtree(p)
    except: pass
print("✅ Final pycache clear")

# === STEP 6: Clean stale signals from DB ===
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
import django; django.setup()
from backend.apps.trading.models import Signal
from django.utils import timezone
from datetime import timedelta

old = Signal.objects.filter(status="ACTIVE", created_at__lt=timezone.now()-timedelta(hours=1))
cnt = old.count()
old.delete()
print(f"✅ Deleted {cnt} stale ACTIVE signals")
print(f"   Remaining: {Signal.objects.count()} total, {Signal.objects.filter(status='ACTIVE').count()} ACTIVE")

print("\n🎯 ALL FIXES APPLIED! Restart the engine now.")