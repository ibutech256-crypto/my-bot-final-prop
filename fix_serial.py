"""Fix SignalSerializer to add confidence_tier field."""
import os, sys, signal
signal.signal(signal.SIGINT, signal.SIG_IGN)

ser_path = r"C:\prop-frim-bot\backend\apps\trading\serializers.py"
with open(ser_path, "r") as f:
    sc = f.read()

# Add confidence_tier to SignalSerializer
old = "class SignalSerializer(serializers.ModelSerializer):\n    symbol_name = serializers.CharField(source=\"symbol.symbol\", read_only=True)\n    class Meta:"
new = """class SignalSerializer(serializers.ModelSerializer):
    symbol_name = serializers.CharField(source="symbol.symbol", read_only=True)
    confidence_tier = serializers.SerializerMethodField()
    def get_confidence_tier(self, obj):
        c = float(obj.confidence)
        if c >= 85: return "VERY_STRONG"
        if c >= 70: return "STRONG"
        if c >= 55: return "VALID"
        if c >= 50: return "EMERGING"
        return "WEAK"
    class Meta:"""

if old in sc:
    sc = sc.replace(old, new)
    with open(ser_path, "w") as f:
        f.write(sc)
    print("confidence_tier added to SignalSerializer")
else:
    print("Pattern not found!")
    idx = sc.find("class SignalSerializer")
    if idx >= 0:
        print(f"Current: {sc[idx:idx+200]}")

import py_compile
try:
    py_compile.compile(ser_path, doraise=True)
    print("SYNTAX: OK")
except Exception as e:
    print(f"SYNTAX ERROR: {e}")

print("\nDONE")
