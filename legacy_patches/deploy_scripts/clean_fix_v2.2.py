"""Apply v2.2 upgrades to engine file from backup."""
import py_compile

content = open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py.v22bak", "r").read()

# FIX 4: Deduplication
old_dedup = 'recent = Signal.objects.filter(symbol=symbol_obj, direction=direction.value, strategy_name=f"Romeo TPT ({tf_enum.value})", created_at__gte=django_tz.now() - django_tz.timedelta(minutes=2)).exists()\n                                        if not recent:'
new_dedup = 'existing_active = Signal.objects.filter(symbol=symbol_obj, direction=direction.value, strategy_name=f"Romeo TPT ({tf_enum.value})", status__in=["ACTIVE_MONITORING", "EXECUTION_READY", "EXECUTING", "EXECUTED", "PROTECTED"]).exists()\n                                        if not existing_active:'
if old_dedup in content:
    content = content.replace(old_dedup, new_dedup)
    print("FIX 4: Deduplication added")
else:
    print("FIX 4: Dedup pattern not found!")

# FIX 5: Replace ACTIVE status with lifecycle_status variable
old_status = 'status="ACTIVE" if is_high_conf or score.total >= Decimal("55") else "WATCHLIST",'
new_status = 'status=lifecycle_status,'
if old_status in content:
    content = content.replace(old_status, new_status)
    print("FIX 5: Status -> lifecycle_status")
else:
    print("FIX 5: Status pattern not found!")

# FIX 6: Add lifecycle computation before Signal.create()
old_create = '                                        sig = Signal.objects.create('
lifecycle_block = (
    '                                        # v2.2: Lifecycle states based on score tier\n'
    '                                        lifecycle_status = "WATCHLIST"\n'
    '                                        if score.total >= Decimal("85"):\n'
    '                                            lifecycle_status = "EXECUTION_READY"  # Priority - skip monitoring\n'
    '                                        elif score.total >= Decimal("70"):\n'
    '                                            lifecycle_status = "EXECUTION_READY"\n'
    '                                        elif score.total >= Decimal("55"):\n'
    '                                            lifecycle_status = "ACTIVE_MONITORING"\n'
    '                                        else:\n'
    '                                            lifecycle_status = "WATCHLIST"\n'
    '                                        ' + old_create
)
if old_create in content:
    content = content.replace(old_create, lifecycle_block, 1)
    print("FIX 6: Lifecycle block added before Signal.create()")
else:
    print("FIX 6: Create pattern not found!")

# FIX 7: Multi-TP
old_tp = 'calc_tp = completed[-1].close + calc_risk * Decimal("2.0") if direction.value == "BUY" else completed[-1].close - calc_risk * Decimal("2.0") '
new_tp = (
    'calc_tp1 = completed[-1].close + calc_risk * Decimal("1.0") if direction.value == "BUY" else completed[-1].close - calc_risk * Decimal("1.0")\n'
    '                                            calc_tp2 = completed[-1].close + calc_risk * Decimal("2.0") if direction.value == "BUY" else completed[-1].close - calc_risk * Decimal("2.0")\n'
    '                                            calc_tp3 = completed[-1].close + calc_risk * Decimal("3.0") if direction.value == "BUY" else completed[-1].close - calc_risk * Decimal("3.0")\n'
    '                                            calc_tp = calc_tp2'
)
if old_tp in content:
    content = content.replace(old_tp, new_tp)
    print("FIX 7: Multi-TP added")
else:
    print("FIX 7: TP pattern not found!")

# FIX 8: Update rationale
old_rationale = 'rationale=f"Score={score.total} Tier1={tier1} Tier2={tier2} Sweep={has_sweep2} KOD={kod} Confluences: {[k for k, v in score.components.items() if v > 0]}",'
new_rationale = 'rationale=f"Score={score.total} T1={tier1} T2={tier2} Sweep={has_sweep2} KOD={kod} TP1={calc_tp1:.5f} TP2={calc_tp2:.5f} TP3={calc_tp3:.5f} RR1={calc_risk:.5f} Confluences: {[k for k, v in score.components.items() if v > 0]}",'
if old_rationale in content:
    content = content.replace(old_rationale, new_rationale)
    print("FIX 8: Rationale updated")
else:
    print("FIX 8: Rationale pattern not found!")

# FIX 9: Confidence sizing
old_lot = 'lot_size = mgr.calculate_position_size(symbol_obj, sig.entry_price, sig.stop_loss)'
new_lot = 'lot_size = mgr.calculate_position_size(symbol_obj, sig.entry_price, sig.stop_loss, sig.confidence)'
if old_lot in content:
    content = content.replace(old_lot, new_lot)
    print("FIX 9: Confidence sizing added")
else:
    print("FIX 9: Lot pattern not found!")

# FIX 10: EXECUTED status
old_exec = 'self.stdout.write(f"TRADE EXECUTED & RECORDED: {sym} {sig.direction} @ {filled_price} (Ticket: #{ticket_str})")'
new_exec = 'Signal.objects.filter(id=sig.id).update(status="EXECUTED")\n                                                                            self.stdout.write(f"TRADE EXECUTED & RECORDED: {sym} {sig.direction} @ {filled_price} (Ticket: #{ticket_str})")'
if old_exec in content:
    content = content.replace(old_exec, new_exec)
    print("FIX 10: EXECUTED status update")
else:
    print("FIX 10: Exec pattern not found!")

# FIX 11: Gate block reasons
old_gate = 'if not passed_gate:\n                                                                    self.stdout.write(f"EXECUTION REJECTED [{sym}]: {gate_msg}")'
new_gate = (
    'if not passed_gate:\n'
    '                                                                    self.stdout.write(f"EXECUTION REJECTED [{sym}]: {gate_msg}")\n'
    '                                                                    block_status = "BLOCKED_SPREAD"\n'
    '                                                                    if "news" in gate_msg.lower():\n'
    '                                                                        block_status = "BLOCKED_NEWS"\n'
    '                                                                    elif "session" in gate_msg.lower():\n'
    '                                                                        block_status = "BLOCKED_SESSION"\n'
    '                                                                    elif "exposure" in gate_msg.lower() or "limit" in gate_msg.lower():\n'
    '                                                                        block_status = "BLOCKED_EXPOSURE"\n'
    '                                                                    Signal.objects.filter(id=sig.id).update(status=block_status)'
)
if old_gate in content:
    content = content.replace(old_gate, new_gate)
    print("FIX 11: Gate block reasons")
else:
    print("FIX 11: Gate pattern not found!")

# FIX 12: Exposure skip
old_skip = 'if not eval_result.trading_allowed:\n                                                            self.stdout.write(f"EXECUTION SKIPPED [{sym}]: {eval_result.reason}")'
new_skip = 'if not eval_result.trading_allowed:\n                                                            self.stdout.write(f"EXECUTION SKIPPED [{sym}]: {eval_result.reason}")\n                                                            Signal.objects.filter(id=sig.id).update(status="BLOCKED_EXPOSURE")'
if old_skip in content:
    content = content.replace(old_skip, new_skip)
    print("FIX 12: Exposure skip logging")
else:
    print("FIX 12: Skip pattern not found!")

# Write
open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "w").write(content)
print("\nFile saved!")

# Check syntax
try:
    py_compile.compile(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", doraise=True)
    print("SYNTAX OK")
except py_compile.PyCompileError as e:
    print(f"SYNTAX ERROR: {e}")
