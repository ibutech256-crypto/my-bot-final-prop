
import signal, py_compile; signal.signal(signal.SIGINT, signal.SIG_IGN)
e = open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py","r").read()
c = 0

# Fix 1: Dedup
o1 = 'recent = Signal.objects.filter(symbol=symbol_obj, direction=direction.value, strategy_name=f"Romeo TPT ({tf_enum.value})", created_at__gte=django_tz.now() - django_tz.timedelta(minutes=2)).exists()\n                                        if not recent:'
n1 = 'recent = Signal.objects.filter(symbol=symbol_obj, direction=direction.value, strategy_name=f"Romeo TPT ({tf_enum.value})", status__in=["ACTIVE","ACTIVE_MONITORING","EXECUTION_READY","EXECUTING","EXECUTED","PROTECTED"], created_at__gte=django_tz.now() - django_tz.timedelta(hours=4)).exists()\n                                        if not recent:'
if o1 in e: e = e.replace(o1,n1); c+=1; print("F1:Dedup")

# Fix 2: Status  
o2 = 'status="ACTIVE" if is_high_conf else "WATCHLIST",'
if o2 in e: e = e.replace(o2,'status=lifecycle_status,'); c+=1; print("F2:Status")

# Fix 3: Lifecycle
o3 = '\n                                        sig = Signal.objects.create('
n3 = '\n                                        lifecycle_status = "WATCHLIST"\n                                        if score.total >= Decimal("85"):\n                                            lifecycle_status = "EXECUTION_READY"\n                                        elif score.total >= Decimal("70"):\n                                            lifecycle_status = "EXECUTION_READY"\n                                        elif score.total >= Decimal("55"):\n                                            lifecycle_status = "ACTIVE_MONITORING"\n                                        else:\n                                            lifecycle_status = "WATCHLIST"\n                                        sig = Signal.objects.create('
if o3 in e: e = e.replace(o3,n3,1); c+=1; print("F3:Lifecycle")

if c>0: open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py","w").write(e)
print(f"{c} fixes applied")

py_compile.compile(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", doraise=True)
print("SYNTAX OK")
e2 = open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py").read()
if "lifecycle_status" in e2: print("LIFECYCLE OK")
