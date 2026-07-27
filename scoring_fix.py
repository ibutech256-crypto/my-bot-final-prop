import signal, os, pathlib, shutil; signal.signal(signal.SIGINT, signal.SIG_IGN)
scoring = open(r"C:\prop-frim-bot\trading_engine\scoring.py","r").read()
if "total = min" not in scoring:
    scoring = scoring.replace('passed = False', 'if not kod:\n            total = min(total, Decimal("70"))\n        passed = False')
    open(r"C:\prop-frim-bot\trading_engine\scoring.py","w").write(scoring)
    print("Scoring v2.2 fixed")
else:
    print("Scoring already v2.2")
