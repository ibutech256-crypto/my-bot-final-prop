
import os, signal, subprocess, sys, time

os.chdir(r"C:\prop-frim-bot")

# 1. Clear cache
os.system('powershell -Command "Get-ChildItem C:\\prop-frim-bot -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue"')

# 2. Add signal handler to engine (idempotent)
p = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
c = open(p).read()
if "SIG_IGN" not in c:
    c = c.replace(
        "from telegram.bot import TelegramBotClient",
        "from telegram.bot import TelegramBotClient\nimport signal, os\ntry:\n    signal.signal(signal.SIGINT, signal.SIG_IGN)\nexcept:\n    pass"
    )
    open(p, "w").write(c)
    print("SIGNAL: Added SIG_IGN handler")

# 3. Verify syntax
import py_compile
try:
    py_compile.compile(p, doraise=True)
    print("SYNTAX: OK")
except Exception as e:
    print(f"SYNTAX: ERROR - {e}")
    sys.exit(1)

# 4. Reconfigure NSSM
os.system('nssm set TradingMT5Engine AppStopMethodOverride 0')
os.system('nssm set TradingMT5Engine AppThrottle 3000')
os.system('nssm set TradingMT5Engine Application C:\\Windows\\System32\\cmd.exe')
os.system('nssm set TradingMT5Engine AppParameters /c C:\\prop-frim-bot\\run_engine.bat')
os.system('nssm set TradingMT5Engine AppDirectory C:\\prop-frim-bot')

# 5. Start engine
os.system('nssm stop TradingMT5Engine')
time.sleep(3)
os.system('nssm start TradingMT5Engine')
time.sleep(5)

# 6. Check status
r = os.popen('nssm status TradingMT5Engine').read().strip()
print(f"STATUS: {r}")

# 7. Check Python process
r = os.popen('powershell -Command "Get-Process python -ErrorAction SilentlyContinue | Select-Object Id"').read().strip()
print(f"PYTHON: {"RUNNING" if r else "NOT RUNNING"}")

# 8. Check log
r = os.popen('powershell -Command "Get-Content C:\\prop-frim-bot\\logs\\TradingMT5Engine.log -Tail 6"').read()
print(f"LOG:\n{r}")

print("\nDONE")
