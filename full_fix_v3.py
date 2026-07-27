import signal, os, shutil, pathlib
signal.signal(signal.SIGINT, signal.SIG_IGN)
os.chdir(r"C:\prop-frim-bot")

# Clear ALL pycache
for p in pathlib.Path(r"C:\prop-frim-bot").rglob("__pycache__"):
    try: shutil.rmtree(p)
    except: pass
for p in pathlib.Path(r"C:\prop-frim-bot\.venv").rglob("__pycache__"):
    try: shutil.rmtree(p)
    except: pass
print("✅ All pycache cleared")

# Read and verify scoring engine
scoring = open(r"C:\prop-frim-bot\trading_engine\scoring.py", "r").read()
if "total = min(total, Decimal" in scoring:
    print("✅ Scoring v2.2: KOD cap present")
else:
    print("❌ Scoring v2.2 missing - needs redeploy")

# Read engine file
engine = open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "r").read()
print(f"Engine file: {len(engine)} chars")

# FIX 1: Dedup - replace 2-min window with 4-hour lifecycle-aware check
old_dedup = 'recent = Signal.objects.filter(symbol=symbol_obj, direction=direction.value, strategy_name=f"Romeo TPT ({tf_enum.value})", created_at__gte=django_tz.now() - django_tz.timedelta(minutes=2)).exists()\n                                        if not recent:'
new_dedup = 'recent = Signal.objects.filter(symbol=symbol_obj, direction=direction.value, strategy_name=f"Romeo TPT ({tf_enum.value})", status__in=["ACTIVE", "ACTIVE_MONITORING", "EXECUTION_READY", "EXECUTING", "EXECUTED", "PROTECTED"], created_at__gte=django_tz.now() - django_tz.timedelta(hours=4)).exists()\n                                        if not recent:'

if old_dedup in engine:
    engine = engine.replace(old_dedup, new_dedup)
    print("✅ FIX 1: Dedup window 2min->4hours + lifecycle status check")
else:
    print("❌ FIX 1: Dedup pattern not found - checking alternatives")
    idx = engine.find("created_at__gte=django_tz.now() - django_tz.timedelta(minutes=2)")
    if idx >= 0:
        print(f"  Found at {idx}: {engine[idx-50:idx+80]}")

# FIX 2: Replace status assignment
old_status = 'status="ACTIVE" if is_high_conf else "WATCHLIST",'
new_status = 'status=lifecycle_status,'
if old_status in engine:
    engine = engine.replace(old_status, new_status)
    print("✅ FIX 2: status -> lifecycle_status")
else:
    print("❌ FIX 2: pattern not found - checking actual status line")
    idx = engine.find('status="ACTIVE"')
    if idx >= 0:
        print(f"  Found at {idx}: {engine[idx:idx+80]}")

# FIX 3: Add lifecycle computation before Signal.create()
old_create = '\n                                        sig = Signal.objects.create('
lifecycle_block = '\n                                        # v2.2: Lifecycle states\n                                        lifecycle_status = "WATCHLIST"\n                                        if score.total >= Decimal("85"):\n                                            lifecycle_status = "EXECUTION_READY"\n                                        elif score.total >= Decimal("70"):\n                                            lifecycle_status = "EXECUTION_READY"\n                                        elif score.total >= Decimal("55"):\n                                            lifecycle_status = "ACTIVE_MONITORING"\n                                        else:\n                                            lifecycle_status = "WATCHLIST"\n                                        sig = Signal.objects.create('

if old_create in engine:
    engine = engine.replace(old_create, lifecycle_block, 1)
    print("✅ FIX 3: Lifecycle block added before Signal.create()")
else:
    print("❌ FIX 3: Create pattern not found - checking")
    idx = engine.find("sig = Signal.objects.create(")
    if idx >= 0:
        context = engine[idx-40:idx+60]
        print(f"  Found at {idx}: {repr(context)}")

# Write engine back
open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "w").write(engine)

# Verify syntax
import py_compile
try:
    py_compile.compile(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", doraise=True)
    print("✅ SYNTAX OK")
except py_compile.PyCompileError as e:
    print(f"❌ SYNTAX ERROR: {e}")

# Also check the engine has the fix
engine2 = open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "r").read()
if "lifecycle_status" in engine2:
    print("✅ Lifecycle code confirmed in engine")
if "lifecycle_status" not in engine2:
    print("❌ Lifecycle code STILL missing!")
    idx = engine2.find("sig = Signal.objects.create(")
    if idx >= 0:
        print(f"  Before create: ...{engine2[idx-200:idx]}...")
