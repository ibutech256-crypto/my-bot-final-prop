"""Fix KeyboardInterrupt crash loop - catch BaseException in network calls."""
content = open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "r").read()

# Fix 1: Telegram heartbeat - catch BaseException instead of Exception
old_hb = """                    except Exception as hb_err:
                        self.stderr.write(f\"Error dispatching 4-hour Telegram heartbeat: {hb_err}\")"""

new_hb = """                    except BaseException as hb_err:
                        if not isinstance(hb_err, KeyboardInterrupt):
                            self.stderr.write(f"Error dispatching Telegram heartbeat: {hb_err}")"""

if old_hb in content:
    content = content.replace(old_hb, new_hb)
    print("Fix 1: Telegram heartbeat exception handler")
else:
    print("Fix 1: Pattern not found!")

# Fix 2: Telegram startup message
old_startup = """                except Exception:
                pass"""
# This is too generic, find the right one
# Let me look for the Telegram startup exception
idx = content.find("except Exception:\n                pass")
if idx > 0:
    # Check if this is near a Telegram send
    context = content[idx-200:idx+50]
    if "send_message" in context or "Telegram" in context or "tg_client" in context:
        # This is a Telegram exception handler
        before = content[idx-200:idx]
        after = content[idx+len("except Exception:\n                pass"):idx+len("except Exception:\n                pass")+50]
        print(f"Found Telegram exception handler at {idx}")
        # Change to BaseException
        new_startup = """                except BaseException:
                    if not isinstance(e, KeyboardInterrupt):
                        pass"""
        # Actually, let's just add KeyboardInterrupt handling to all tg_client calls
        # A simpler approach: wrap the handler

# Actually, let me just add a global KeyboardInterrupt shield around all Telegram operations
# Find all tg_client.send_message calls and ensure their exception handlers catch BaseException

# Fix 3: Trade execution Telegram message
old_exec_tg = """                                                                                for sub in subscribers:
                                                                                    try:
                                                                                        tg_client.send_message(sub.chat_id, exec_msg)
                                                                                    except Exception:
                                                                                        pass"""

new_exec_tg = """                                                                                for sub in subscribers:
                                                                                    try:
                                                                                        tg_client.send_message(sub.chat_id, exec_msg)
                                                                                    except BaseException:
                                                                                        pass"""

if old_exec_tg in content:
    content = content.replace(old_exec_tg, new_exec_tg)
    print("Fix 3: Trade exec Telegram handler")
else:
    print("Fix 3: Pattern not found!")

# Fix 4: Signal Telegram broadcast
old_sig_tg = """                                                        for s in subscribers:
                                                            try:
                                                                tg_client.send_message(s.chat_id, msg)
                                                            except Exception:
                                                                pass"""

new_sig_tg = """                                                        for s in subscribers:
                                                            try:
                                                                tg_client.send_message(s.chat_id, msg)
                                                            except BaseException:
                                                                pass"""

if old_sig_tg in content:
    content = content.replace(old_sig_tg, new_sig_tg)
    print("Fix 4: Signal Telegram handler")
else:
    print("Fix 4: Pattern not found!")

# Fix 5: Outcome Telegram handler
old_out_tg = """                                for sub in subscribers:
                                        try:
                                            tg_client.send_message(sub.chat_id, out_msg)
                                        except Exception:
                                            pass"""

new_out_tg = """                                for sub in subscribers:
                                        try:
                                            tg_client.send_message(sub.chat_id, out_msg)
                                        except BaseException:
                                            pass"""

if old_out_tg in content:
    content = content.replace(old_out_tg, new_out_tg)
    print("Fix 5: Outcome Telegram handler")
else:
    print("Fix 5: Pattern not found!")

# Write
open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "w").write(content)

import py_compile
try:
    py_compile.compile(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", doraise=True)
    print("SYNTAX OK!")
except py_compile.PyCompileError as e:
    print(f"SYNTAX ERROR: {e}")
