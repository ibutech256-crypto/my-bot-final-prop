"""Fix indentation errors in mt5_client.py and signal_freshness.py."""
import os, sys, signal
signal.signal(signal.SIGINT, signal.SIG_IGN)

# ===== FIX mt5_client.py =====
print("=== FIX mt5_client.py ===")
path = r"C:\prop-frim-bot\broker_engine\mt5_client.py"
lines = open(path, "r").readlines()

print(f"Total lines: {len(lines)}")
print("Lines 85-95:")
for i in range(84, min(95, len(lines))):
    print(f"  {i+1}: {repr(lines[i][:80])}")

# Find the indentation issue
for i, line in enumerate(lines):
    if "def place_market_order" in line:
        print(f"\nplace_market_order at line {i+1}")
        # Check indentation of the function
        expected_indent = len(line) - len(line.lstrip())
        print(f"  Function indent: {expected_indent}")
        
        # Check lines after function
        for j in range(i+1, min(i+5, len(lines))):
            ai = len(lines[j]) - len(lines[j].lstrip())
            print(f"  Line {j+1}: indent={ai} |{lines[j][:60]}")

# The issue is likely the new function has wrong indentation
# Let me read the full file and look for the problem
content = open(path, "r").read()

# The function might have been inserted at wrong indent level
# Let me replace the entire problematic section
idx = content.find("def place_market_order")
if idx >= 0:
    # Find the next function after this one
    next_func = content.find("\ndef ", idx + 10)
    if next_func < 0:
        next_func = len(content)
    
    old_section = content[idx:next_func]
    print(f"\nFound function from {idx} to {next_func}")
    print(f"First few lines:\n{old_section[:200]}")
    
    # Check what indent level the function is at
    first_line = old_section.split('\n')[0]
    indent = len(first_line) - len(first_line.lstrip())
    print(f"Function indent: {indent}")
    
    # If indent is wrong (should be 4 spaces for class method)
    if indent != 4:
        print(f"Fixing indentation from {indent} to 4")
        lines_list = old_section.split('\n')
        fixed_lines = []
        for l in lines_list:
            if l.strip():
                ai = len(l) - len(l.lstrip())
                # Preserve relative indentation
                relative = ai - indent
                fixed_lines.append(" " * (4 + relative) + l.lstrip())
            else:
                fixed_lines.append(l)
        new_section = '\n'.join(fixed_lines)
        content = content[:idx] + new_section + content[next_func:]
        open(path, "w").write(content)
        print("Fixed!")
    else:
        print("Indent looks correct (4) - checking body...")

# ===== FIX signal_freshness.py =====
print("\n=== FIX signal_freshness.py ===")
sf_path = r"C:\prop-frim-bot\system\signal_freshness.py"
sf_lines = open(sf_path, "r").readlines()

print(f"Total lines: {len(sf_lines)}")
print("Lines 70-85:")
for i in range(69, min(85, len(sf_lines))):
    print(f"  {i+1}: {repr(sf_lines[i][:80])}")

# Find the problem - likely the json.dumps block was inserted incorrectly
sf_content = open(sf_path, "r").read()

# Check if there's a 'try' without 'except' or the json block is inside a try
if "try:" in sf_content and "log_entry" in sf_content:
    # Find the context
    try_idx = sf_content.rfind("try:", 0, sf_content.find("log_entry"))
    if try_idx >= 0:
        end_try = sf_content.find("\n", try_idx)
        after_try = sf_content[end_try:end_try+500]
        print(f"Context around try/except:\n{after_try[:300]}")

# The issue is the json.dumps block was inserted after a try: without an except block
# Let me read the original structure and fix it
if "except:" in sf_content and "log_entry" in sf_content:
    # It should be fine - check if try has matching except
    pass

# Re-read and fix the signal_freshness.py carefully
with open(sf_path, "r") as f:
    sf_content = f.read()

# The json.dumps block needs to be inside the `if should_archive:` block
# and should be properly indented
# Let me check what came before
idx = sf_content.find("sig.status = \"EXPIRED\"")
if idx >= 0:
    context = sf_content[idx:idx+500]
    print(f"\nContext around EXPIRED:\n{context[:300]}")

# Fix the block
old_block = '''            sig.status = "EXPIRED"
            # Structured JSON log for expired signal diagnostics
            log_entry = {'''
new_block = '''            sig.status = "EXPIRED"
            # Structured JSON log for expired signal diagnostics
            try:
                log_entry = {'''

if old_block in sf_content:
    sf_content = sf_content.replace(old_block, new_block)
    
    # Also fix the closing of the block - ensure it has except
    if "lf.write" in sf_content:
        # Add the try/except wrapping
        old_json_close = '''            import json, os'''
        new_json_close = '''            except:
                pass'''

# Actually, let me take a simpler approach - just check and rewrite properly        
idx = sf_content.find("log_entry = {")
if idx >= 0:
    # Find the surrounding context
    print(f"\nFound log_entry at {idx}")
    print(sf_content[idx-30:idx+200])

# Let me just remove the broken json block and re-add it properly
# Find the exact broken section
old_broken = sf_content[idx:sf_content.find("\n", sf_content.find("lf.write", idx)) + 100]
print(f"\nBroken section:\n{old_broken[:300]}")

# The problem is the json block was inserted inside a try block without proper indentation
# Let me replace it entirely with a properly formatted version
try:
    # Remove the broken json block
    json_start = sf_content.find('            log_entry = {')
    if json_start >= 0:
        json_end = sf_content.find('\n            ', json_start + 200)
        if json_end < 0:
            json_end = len(sf_content)
        
        # Find the actual end of the json writing block
        write_pos = sf_content.find("lf.write", json_start)
        if write_pos >= 0:
            end_line = sf_content.find("\n", write_pos)
            json_end = end_line + 1
        
        broken = sf_content[json_start:json_end]
        print(f"\nRemoving broken block:\n{broken[:200]}")
        
        proper = '''            # Structured JSON log for expired signal diagnostics (v3.1)
            try:
                log_entry = {
                    "signal_id": f"{sig.symbol.symbol}_{sig.id}",
                    "symbol": sig.symbol.symbol,
                    "final_state": "EXPIRED",
                    "primary_blocking_reason": reason or "AGE_LIMIT_EXCEEDED",
                    "confidence_score": float(sig.confidence) / 100.0,
                    "age_minutes": round(age_minutes, 1),
                }
                import json as _json
                import pathlib
                log_path = __import__("os").path.join(__import__("os").path.dirname(__file__), "..", "logs", "expired_signals.jsonl")
                __import__("os").makedirs(__import__("os").path.dirname(log_path), exist_ok=True)
                with open(log_path, "a") as lf:
                    lf.write(_json.dumps(log_entry) + "\\n")
            except:
                pass'''
        
        sf_content = sf_content.replace(broken, proper)
        open(sf_path, "w").write(sf_content)
        print("Fixed signal_freshness.py")
except Exception as e:
    print(f"Error fixing signals: {e}")

# ===== VERIFY =====
print("\n=== VERIFY ===")
import py_compile
for f in ["C:\\prop-frim-bot\\broker_engine\\mt5_client.py", "C:\\prop-frim-bot\\system\\signal_freshness.py"]:
    try:
        py_compile.compile(f, doraise=True)
        print(f"  {os.path.basename(f)}: OK")
    except Exception as e:
        print(f"  {os.path.basename(f)}: ERROR - {e}")

print("\nDONE")
