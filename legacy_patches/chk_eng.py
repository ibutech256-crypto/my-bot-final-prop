import os, subprocess
os.chdir("C:/prop-frim-bot/logs")

# Check engine running
print("=== ENGINE STATUS ===")

# Most recent log lines
r = subprocess.run(["python", "-c", "import os;f=open('TradingMT5Engine.log','rb');sz=os.fstat(f.fileno()).st_size;f.seek(max(0,sz-2000));print(f.read().decode('latin-1')[-1500:]);f.close()"], capture_output=True, text=True, cwd="C:/prop-frim-bot/logs")
print(r.stdout[-1500:])

print("\n=== RECENT KEY EVENTS ===")
r2 = subprocess.run(["findstr", "/C:", "NEW SIGNAL RECORDED"], capture_output=True, text=True)
if r2.stdout.strip():
    lines = [l for l in r2.stdout.split("\n") if l.strip()]
    print(f"New signals: {len(lines)}")
    for l in lines[-3:]:
        print(f"  {l[:130]}")

r3 = subprocess.run(["findstr", "/C:", "BLOCKED BY"], capture_output=True, text=True)
if r3.stdout.strip():
    lines = [l for l in r3.stdout.split("\n") if "BLOCKED" in l]
    print(f"Blocked: {len(lines)}")
    for l in lines[-3:]:
        print(f"  {l[:130]}")

r4 = subprocess.run(["findstr", "/C:", "TRADE EXECUTED"], capture_output=True, text=True)
if r4.stdout.strip():
    lines = [l for l in r4.stdout.split("\n") if "TRADE EXECUTED" in l]
    print(f"Trades: {len(lines)}")
    for l in lines[-3:]:
        print(f"  {l[:150]}")
else:
    print("Trades: 0 in this sample")
    # Check if engine is scanning
    r5 = subprocess.run(["findstr", "/C:", "NEW SIGNAL"], capture_output=True, text=True)
    if r5.stdout.strip():
        print("Engine is creating signals - execution gates blocking")
    else:
        print("No signals either - engine may be in startup")

