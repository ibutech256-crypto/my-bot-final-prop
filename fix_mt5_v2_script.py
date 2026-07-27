import re
with open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "r") as f:
    content = f.read()

# Add mt5_spec definition before the spread protection gates
# Replace: "# Spread Protection Gates" with "mt5_spec = client.mt5.symbol_info(sym)\n# Spread Protection Gates"
old = "# Spread Protection Gates & Spread-to-Target Ratio (v1.9.2)"
new = "mt5_spec = client.mt5.symbol_info(sym)\n                                            # Spread Protection Gates & Spread-to-Target Ratio (v1.9.2)"

if old in content:
    content = content.replace(old, new, 1)
    print("mt5_spec fix applied!")
else:
    print("Pattern NOT found - searching...")
    if "Spread Protection" in content:
        print("Spread Protection text exists")
    # Show context
    idx = content.find("mt5_spec.point")
    if idx > 0:
        print("Context around mt5_spec.point:")
        print(repr(content[idx-200:idx+100]))

with open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "w") as f:
    f.write(content)
print("Done")
