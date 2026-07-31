"""Verify whether confidence is passed to calculate_position_size."""
import os, sys
sys.path.insert(0, "C:\\prop-frim-bot")

with open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "r") as f:
    lines = f.readlines()

print("=== Lines containing calculate_position_size ===")
for i, line in enumerate(lines):
    if "calculate_position_size" in line:
        print(f"  Line {i+1}: {line.rstrip()}")

# Also check the AccountManager signature
with open(r"C:\prop-frim-bot\trading_engine\account_manager.py", "r") as f:
    content = f.read()

print("\n=== AccountManager.calculate_position_size signature ===")
for line in content.split('\n'):
    if "def calculate_position_size" in line:
        print(f"  {line}")
        break

# Calculate expected lot manually
from decimal import Decimal, ROUND_DOWN
equity = Decimal("5056.87")
min_lot = Decimal("0.01")
lot_step = Decimal("0.01")

# Growing personal calculation
raw = (equity / Decimal("1000")) * Decimal("0.05")
safety_max = Decimal("0.05")
print(f"\n=== MANUAL POSITION SIZE CALCULATION ===")
print(f"Equity: ${equity}")
print(f"Raw lots (equity/1000 * 0.05): {raw}")
print(f"Capped at safety_max (0.05): {min(raw, safety_max)}")

step1 = min(raw, safety_max)
step2 = (step1 / lot_step).to_integral_value(rounding=ROUND_DOWN) * lot_step
step2 = max(min_lot, step2)
print(f"After rounding: {step2}")

# With confidence=88
conf = Decimal("88")
if conf >= Decimal("95"): cm = Decimal("1.00")
elif conf >= Decimal("85"): cm = Decimal("0.75")
elif conf >= Decimal("70"): cm = Decimal("0.50")
elif conf >= Decimal("55"): cm = Decimal("0.35")
else: cm = Decimal("0.20")
print(f"Confidence: {conf}")
print(f"Confidence multiplier: {cm}")

step3 = (step2 * cm / lot_step).to_integral_value(rounding=ROUND_DOWN) * lot_step
step3 = max(min_lot, step3)
print(f"After confidence scaling: {step3}")

# With default confidence (55)
conf2 = Decimal("55")
if conf2 >= Decimal("95"): cm2 = Decimal("1.00")
elif conf2 >= Decimal("85"): cm2 = Decimal("0.75")
elif conf2 >= Decimal("70"): cm2 = Decimal("0.50")
elif conf2 >= Decimal("55"): cm2 = Decimal("0.35")
else: cm2 = Decimal("0.20")
print(f"\nWith default confidence (55):")
print(f"Confidence multiplier: {cm2}")
step3b = (step2 * cm2 / lot_step).to_integral_value(rounding=ROUND_DOWN) * lot_step
step3b = max(min_lot, step3b)
print(f"Final lot: {step3b}")
