
import os, signal, subprocess, sys, time
os.chdir(r"C:\prop-frim-bot")
os.system('powershell -Command "Get-ChildItem C:\\prop-frim-bot -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue"')
p = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
c = open(p).read()
if "SIG_IGN" not in c:
    c = c.replace(
        "from telegram.bot import TelegramBotClient",
        "from telegram.bot import TelegramBotClient\nimport signal, os\ntry:\n    signal.signal(signal.SIGINT, signal.SIG_IGN)\nexcept:\n    pass"
    )
    open(p, "w").write(c)
    print("SIGNAL: Added SIG_IGN")
import py_compile
try:
    py_compile.compile(p, doraise=True)
    print("SYNTAX: OK")
except Exception as e:
    print("SYNTAX ERROR:", e)
    sys.exit(1)
os.system('nssm set TradingMT5Engine AppStopMethodOverride 0')
os.system('nssm set TradingMT5Engine AppThrottle 3000')
os.system('nssm stop TradingMT5Engine')
time.sleep(3)
os.system('nssm start TradingMT5Engine')
time.sleep(5)
r = os.popen('nssm status TradingMT5Engine').read().strip()
print("STATUS:", r)
r = os.popen('powershell -Command "Get-Process python -ErrorAction SilentlyContinue | Select-Object Id"').read().strip()
print("PYTHON:", "RUNNING" if r else "NOT RUNNING")
r = os.popen('powershell -Command "Get-Content C:\\prop-frim-bot\\logs\\TradingMT5Engine.log -Tail 6"').read()
print("LOG:", r)
print("DONE")
