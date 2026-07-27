"""Disable Adaptive Brain evaluate method - v2 with correct signature."""
content = open(r"C:\prop-frim-bot\trading_engine\adaptive_brain.py", "r").read()

# The actual method signature uses 'confidence_score' not 'score'
old = '    def evaluate(self, symbol: str, confidence_score: Decimal) -> Tuple[bool, str, Decimal]:\n'
old += '        """\n'
old += '        Evaluates a candidate trade against the real-time Adaptive Brain backtest memory.\n'
old += '        Returns: (passed_gate, rationale_or_reason, sizing_multiplier)\n'
old += '        """\n'
old += '        import time\n'

new = '    def evaluate(self, symbol: str, confidence_score: Decimal) -> Tuple[bool, str, Decimal]:\n'
new += '        return True, "ADAPTIVE BRAIN: PASS (disabled)", Decimal("1.0")\n'

if old in content:
    content = content.replace(old, new)
    with open(r"C:\prop-frim-bot\trading_engine\adaptive_brain.py", "w") as f:
        f.write(content)
    print("✅ Adaptive Brain evaluate() disabled successfully!")
else:
    print("Could not match method. Checking what's there...")
    if "def evaluate" in content:
        idx = content.find("def evaluate")
        print(repr(content[idx:idx+400]))
    else:
        print("'def evaluate' NOT found!")
