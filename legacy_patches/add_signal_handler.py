import signal, os
signal.signal(signal.SIGINT, signal.SIG_IGN)
p = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
c = open(p).read()
if "SIG_IGN" not in c:
    c = c.replace(
        "from telegram.bot import TelegramBotClient",
        "from telegram.bot import TelegramBotClient\nimport signal, os\ntry:\n    signal.signal(signal.SIGINT, signal.SIG_IGN)\nexcept:\n    pass"
    )
    open(p, "w").write(c)
    print("SIGNAL HANDLER ADDED")
else:
    print("ALREADY PRESENT")
import py_compile
try:
    py_compile.compile(p, doraise=True)
    print("SYNTAX OK")
except Exception as e:
    print(f"SYNTAX ERROR: {e}")
