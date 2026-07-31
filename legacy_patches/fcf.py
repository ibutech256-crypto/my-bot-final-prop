import os, py_compile
os.chdir("C:/prop-frim-bot")
p = "backend/apps/trading/management/commands/run_mt5_engine.py"
c = open(p, "r", encoding="utf-8").read()

# The crash is: there's a "try:" without "except" near line 447
# Find the broken area
idx = c.find("try:\n                                            if not recent:")
if idx > 0:
    print("Found broken try/except at", idx)
    # Remove the misplaced "try:"
    c = c[:idx] + c[idx:].replace("try:\n                                            ", "")
    print("Removed stray try block")
else:
    # Try alternative pattern
    idx2 = c.find("try:\n                                        if not recent:")
    if idx2 > 0:
        print("Found at", idx2)
        c = c[:idx2] + c[idx2:].replace("try:\n                                        ", "")
    else:
        idx3 = c.find("try:\n                                    if not recent:")
        if idx3 > 0:
            c = c[:idx3] + c[idx3:].replace("try:\n                                    ", "")
            print("Found and fixed at", idx3)
        else:
            print("Pattern not found - checking...")
            for i, l in enumerate(c.split('\n')):
                if 'if not recent:' in l:
                    # Show surrounding lines
                    for j in range(max(0,i-3), min(len(c.split('\n')), i+3)):
                        line = c.split('\n')[j]
                        print(f"  L{j+1}: {line[:120]}")
                    break

# Verify
try:
    py_compile.compile(p, doraise=True)
    print("SYNTAX OK!")
except py_compile.PyCompileError as e:
    print(f"ERROR: {e}")

with open(p, "w", encoding="utf-8") as f:
    f.write(c)
print("File saved")
