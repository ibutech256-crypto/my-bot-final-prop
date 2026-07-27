import os, sys

p = "C:/prop-frim-bot/backend/apps/trading/management/commands/run_mt5_engine.py"

with open(p, "rb") as f:
    c = f.read()

# Find the exact block byte by byte
idx = c.find(b"Spread Protection Gates")
print(f"Found at byte {idx}")

# Show the exact bytes
start = idx
end = c.find(b"calc_tp = completed", start)
if end < 0:
    end = start + 500
print(f"End marker at byte {end}")

# Extract the exact block
block = c[start:end]
print(f"Block is {len(block)} bytes")
print(f"First 100 bytes repr: {repr(block[:100])}")
print(f"Last 100 bytes repr: {repr(block[-100:])}")

# Also check what follows
after = c[end:end+200]
print(f"\nAfter block: {repr(after[:200])}")

# Now find exactly what we need to replace
# We need to replace from the line with "Spread Protection Gates" to the line with "calc_tp = completed"
# Find the start of the line containing "Spread Protection Gates"
line_start = c.rfind(b"\n", 0, start) + 1
# The end should be just before "calc_tp = completed"
line_end = end

print(f"\nLine start at {line_start}, replacing to {line_end}")
replacement = b'# SL calc (no mt5_spec dependency)\n                                            atr_buffer = Decimal("1.5") * atr\n                                            calc_sl = (min(completed[-1].low, crt_range.low) - atr_buffer) if direction.value == "BUY" else (max(completed[-1].high, crt_range.high) + atr_buffer)\n                                            calc_risk = abs(completed[-1].close - calc_sl)\n                                            if calc_risk <= 0:\n                                                calc_risk = Decimal("0.001")\n                                            '

new_c = c[:line_start] + replacement + c[line_end:]
with open(p, "wb") as f:
    f.write(new_c)
print(f"\nFIXED! Replaced {line_end - line_start} bytes with {len(replacement)} byte fix")

# Verify
with open(p, "rb") as f:
    c2 = f.read()
if b"mt5_spec" in c2:
    idx2 = c2.find(b"mt5_spec")
    print(f"WARNING: mt5_spec still found at byte {idx2}!")
    print(c2[max(0,idx2-50):idx2+50])
else:
    print("CONFIRMED: No mt5_spec references remain in file!")

import py_compile
try:
    py_compile.compile(p, doraise=True)
    print("SYNTAX OK!")
except py_compile.PyCompileError as e:
    print(f"SYNTAX ERROR: {e}")
