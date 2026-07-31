
import signal
signal.signal(signal.SIGINT, signal.SIG_IGN)
p = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
c = open(p).read()

# Add SIG_IGN handler
if "SIG_IGN" not in c:
    c = c.replace(
        "from telegram.bot import TelegramBotClient",
        "from telegram.bot import TelegramBotClient\nimport signal, os\ntry:\n    signal.signal(signal.SIGINT, signal.SIG_IGN)\nexcept:\n    pass\n"
    )
    print("SIG_IGN added")

# Replace status line
if 'status="ACTIVE" if is_high_conf else "WATCHLIST",' in c:
    c = c.replace('status="ACTIVE" if is_high_conf else "WATCHLIST",', 'status=lifecycle_status,')
    print("Status replaced")
elif 'status="ACTIVE" if is_high_conf or score.total >= Decimal("55") else "WATCHLIST",' in c:
    c = c.replace('status="ACTIVE" if is_high_conf or score.total >= Decimal("55") else "WATCHLIST",', 'status=lifecycle_status,')
    print("Status replaced (alt)")

# Add lifecycle before Signal.create
old = '                                        sig = Signal.objects.create('
new = '                                        # v2.2 Lifecycle\n                                        if score.total >= Decimal("85"):\n                                            lifecycle_status = "EXECUTION_READY"\n                                        elif score.total >= Decimal("70"):\n                                            lifecycle_status = "EXECUTION_READY"\n                                        elif score.total >= Decimal("55"):\n                                            lifecycle_status = "ACTIVE_MONITORING"\n                                        else:\n                                            lifecycle_status = "WATCHLIST"\n                                        sig = Signal.objects.create('
if old in c:
    c = c.replace(old, new, 1)
    print("Lifecycle block added")
else:
    print("Create pattern NOT found - checking...")
    idx = c.find("sig = Signal.objects.create(")
    if idx >= 0:
        print(f"Found at {idx}")
        print(repr(c[idx-50:idx+30]))

# Fix dedup window
old2 = 'recent = Signal.objects.filter(symbol=symbol_obj, direction=direction.value, strategy_name=f"Romeo TPT ({tf_enum.value})", created_at__gte=django_tz.now() - django_tz.timedelta(minutes=2)).exists()\n                                        if not recent:'
new2 = 'recent = Signal.objects.filter(symbol=symbol_obj, direction=direction.value, strategy_name=f"Romeo TPT ({tf_enum.value})", status__in=["ACTIVE","ACTIVE_MONITORING","EXECUTION_READY","EXECUTING","EXECUTED","PROTECTED"], created_at__gte=django_tz.now() - django_tz.timedelta(hours=4)).exists()\n                                        if not recent:'
if old2 in c:
    c = c.replace(old2, new2)
    print("Dedup window extended")
else:
    print("Dedup pattern not found")

open(p, "w").write(c)
print("Engine written")

import py_compile
try:
    py_compile.compile(p, doraise=True)
    print("SYNTAX OK")
except Exception as e:
    print(f"SYNTAX ERROR: {e}")

# Verify
c2 = open(p).read()
if "lifecycle_status" in c2:
    print("LIFECYCLE CONFIRMED in engine")
if "SIG_IGN" in c2:
    print("SIG_IGN CONFIRMED in engine")
