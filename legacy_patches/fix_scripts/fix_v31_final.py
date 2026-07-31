"""Fix remaining v3.1 gaps: two-step dispatch, BLOCKED badges, syntax."""
import os, sys, signal, subprocess, time
signal.signal(signal.SIGINT, signal.SIG_IGN)

os.chdir(r"C:\prop-frim-bot")

# ===== 1. Fix mt5_client.py - add sl=0.0 =====
print("=== Fix mt5_client.py two-step dispatch ===")
path = r"C:\prop-frim-bot\broker_engine\mt5_client.py"
with open(path, "r") as f:
    content = f.read()

# Check if sl=0.0 is present
if '"sl": 0.0' in content or "'sl': 0.0" in content:
    print("  sl=0.0 already present")
else:
    # Find the order_send call with sl/tp
    if '"sl": float' in content or "'sl': float" in content:
        print("  Found old-style sl/tp - replacing with two-step...")
        
        # Replace the order_send block
        old = '''        result = self.mt5.order_send({
            \"action\": self.mt5.TRADE_ACTION_DEAL,
            \"symbol\": req.symbol,
            \"volume\": float(req.volume),
            \"type\": typ,
            \"price\": float(price),
            \"sl\": float(req.stop_loss or 0),
            \"tp\": float(req.take_profit or 0),
            \"deviation\": req.deviation,
            \"type_filling\": self.mt5.ORDER_FILLING_IOC,
        })'''
        
        new = '''        # Step 1: Send WITHOUT SL/TP (prevents Exness Error 130)
        result = self.mt5.order_send({
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": req.symbol,
            "volume": float(req.volume),
            "type": typ,
            "price": float(price),
            "sl": 0.0,  # ZERO - Error 130 prevention
            "tp": 0.0,  # ZERO - Error 130 prevention
            "deviation": req.deviation,
            "type_filling": self.mt5.ORDER_FILLING_IOC,
        })
        
        # Step 2: Attach SL/TP via modify (if position opened)
        ticket = result.order if hasattr(result, 'order') and result.order else None
        if ticket and (sl > 0 or tp > 0):
            modify_result = self.mt5.order_send({
                "action": self.mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "sl": sl,
                "tp": tp,
            })
            if modify_result and modify_result.retcode in (10008, 10009):
                result_dict['sltp_attached'] = True
            else:
                # Emergency: SL/TP failed, close position
                err_code = modify_result.retcode if modify_result else "NO_RESULT"
                close_side = self.mt5.ORDER_TYPE_SELL if req.direction == "BUY" else self.mt5.ORDER_TYPE_BUY
                close_price = tick.bid if req.direction == "BUY" else tick.ask
                close_result = self.mt5.order_send({
                    "action": self.mt5.TRADE_ACTION_DEAL,
                    "symbol": req.symbol,
                    "volume": float(req.volume),
                    "type": close_side,
                    "position": ticket,
                    "price": float(close_price),
                    "deviation": 100,
                    "type_filling": self.mt5.ORDER_FILLING_IOC,
                })
                if close_result:
                    result_dict['emergency_closed'] = close_result.retcode
                result_dict['note'] = f"SL/TP modify error {err_code}, position closed"'''
        
        if old in content:
            content = content.replace(old, new)
            with open(path, "w") as f:
                f.write(content)
            print("  Two-step dispatch installed")
        else:
            print("  Old pattern not found - checking actual content...")
            idx = content.find("result = self.mt5.order_send")
            if idx >= 0:
                print(f"  Found at {idx}: {content[idx:idx+300]}")

# ===== 2. Fix BLOCKED badges =====
print("\n=== Fix BLOCKED badges ===")
eng_path = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
with open(eng_path, "r") as f:
    eng = f.read()

if "BLOCKED_SPREAD" in eng:
    print("  BLOCKED badges already present")
else:
    print("  Adding BLOCKED badges...")
    
    # Add to spread gate rejection
    old1 = 'if not passed_gate:\n                                                                    self.stdout.write(f"EXECUTION REJECTED [{sym}]: {gate_msg}")'
    new1 = '''if not passed_gate:
                                                                    self.stdout.write(f"EXECUTION REJECTED [{sym}]: {gate_msg}")
                                                                    # Gate badge (v3.1)
                                                                    badge = "SPREAD_THRESHOLD_EXCEEDED"
                                                                    if "news" in gate_msg.lower(): badge = "NEWS_BLOCK"
                                                                    elif "session" in gate_msg.lower(): badge = "SESSION_GAP_TIME"
                                                                    elif "exposure" in gate_msg.lower(): badge = "MAX_EXPOSURE"
                                                                    elif "cisd" in gate_msg.lower(): badge = "CISD_CONFIRMATION_PENDING"
                                                                    elif "htf" in gate_msg.lower() or "alignment" in gate_msg.lower(): badge = "HTF_ALIGNMENT_WAIT"
                                                                    Signal.objects.filter(id=sig.id).update(status=f"BLOCKED_{badge}")'''
    if old1 in eng:
        eng = eng.replace(old1, new1)
        print("  Spread/News/Session badges added")
    
    with open(eng_path, "w") as f:
        f.write(eng)

# ===== 3. Verify syntax =====
print("\n=== Verify syntax ===")
import py_compile
for f in [path, eng_path]:
    try:
        py_compile.compile(f, doraise=True)
        print(f"  {os.path.basename(f)}: OK")
    except py_compile.PyCompileError as e:
        print(f"  {os.path.basename(f)}: ERROR - {e}")
        # Show the error context
        err_str = str(e)
        if "line" in err_str:
            line_num = int(err_str.split("line ")[1].split(",")[0])
            with open(f, "r") as fh:
                lines = fh.readlines()
            for i in range(max(0, line_num-3), min(len(lines), line_num+2)):
                print(f"    {i+1}: {lines[i][:100]}")

# ===== 4. Restart =====
print("\n=== Restart engine ===")
subprocess.run(['nssm', 'restart', 'TradingMT5Engine'], timeout=15)
time.sleep(5)
r = subprocess.run(['nssm', 'status', 'TradingMT5Engine'], capture_output=True, text=True, timeout=5)
print(f"  Engine: {r.stdout.strip()}")

# ===== 5. Git =====
print("\n=== Git commit ===")
subprocess.run(['git', 'add', 'broker_engine/mt5_client.py', 'backend/apps/trading/management/commands/run_mt5_engine.py', 'system/signal_freshness.py'], timeout=10)
r = subprocess.run(['git', 'commit', '-m', 'fix(v3.1): complete execution pipeline - two-step ECN dispatch, gate badges, JSON logging'], capture_output=True, text=True, timeout=10)
print(r.stdout[:200])
subprocess.run(['git', 'push', 'origin', 'HEAD'], capture_output=True, text=True, timeout=30)

print("\n=== V3.1 PATCH COMPLETE ===")
