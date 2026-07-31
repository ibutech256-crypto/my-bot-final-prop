import signal, os, shutil, pathlib
signal.signal(signal.SIGINT, signal.SIG_IGN)

# Clear pycache
for p in pathlib.Path(r"C:\prop-frim-bot").rglob("__pycache__"):
    try: shutil.rmtree(p); print(f"Removed {p}")
    except: pass
print("CACHE CLEARED")
