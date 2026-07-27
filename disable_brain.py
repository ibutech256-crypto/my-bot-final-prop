import os, sys
sys.path.insert(0, "C:\\prop-frim-bot")

content = open(r"C:\\prop-frim-bot\\trading_engine\\adaptive_brain.py", "r").read()

# Find the evaluate method and replace it
old = '    def evaluate(self, symbol: str, score: Decimal) -> Tuple[bool, str, Decimal]:\n'
old += '        if score < self.base_threshold:\n'
old += '            return False, f"ADAPTIVE THRESHOLD: current score {score} < dynamic threshold {self.dynamic_threshold:.2f}", 0\n'
old += '        if symbol in self.quarantine_symbols:\n'
old += '            return False, f"SYMBOL QUARANTINED: {symbol} blocked by adaptive brain (recent losses)", self.sizing_multiplier\n'
old += '        self.sync_backtest_memory()\n'
old += '        return True, f"ADAPTIVE BRAIN APPROVED: Score {score} >= {self.dynamic_threshold:.2f} (Base: {self.base_threshold})", self.sizing_multiplier'

new = '    def evaluate(self, symbol: str, score: Decimal) -> Tuple[bool, str, Decimal]:\n'
new += '        return True, "ADAPTIVE BRAIN: PASS (disabled)", Decimal("1.0")'

if old in content:
    content = content.replace(old, new)
    with open(r"C:\\prop-frim-bot\\trading_engine\\adaptive_brain.py", "w") as f:
        f.write(content)
    print("Adaptive Brain evaluate() DISABLED successfully!")
else:
    print("Could not find evaluate method to replace!")
    if "def evaluate" in content:
        print("'def evaluate' found in file")
        # Show what's there
        idx = content.find("def evaluate")
        print(content[idx:idx+300])
    else:
        print("'def evaluate' NOT found!")
