"""Fix mt5_client.py - remove duplicate function at wrong indent."""
import os, sys

path = r"C:\prop-frim-bot\broker_engine\mt5_client.py"
with open(path, "r") as f:
    content = f.read()

# The problem: the function was inserted at indent 12 (inside _check_spread_safety)
# We need to find both copies and keep only the correct one (indent 4)

# Count occurrences of place_market_order
count = content.count("def place_market_order")
print(f"Found {count} copies of place_market_order")

# Find all occurrences
indices = []
idx = 0
while True:
    idx = content.find("def place_market_order", idx)
    if idx < 0:
        break
    indices.append(idx)
    idx += 1

for i, pos in enumerate(indices):
    line_num = content[:pos].count('\n') + 1
    indent = len(content[pos:]) - len(content[pos:].lstrip())
    if pos > 0:
        indent = len(content[pos:content.find('\n', pos)]) - len(content[pos:content.find('\n', pos)].lstrip())
        # Get the actual line
        start = content.rfind('\n', 0, pos) + 1
        line = content[start:content.find('\n', start)]
        indent = len(line) - len(line.lstrip())
    print(f"  Copy {i+1} at byte {pos}, line {line_num}, indent={indent}")

# If there are 2 copies, remove the one at indent 12
if count > 1:
    # Find the one at wrong indent
    for i, pos in enumerate(indices):
        start = content.rfind('\n', 0, pos) + 1
        line_end = content.find('\n', start)
        line = content[start:line_end]
        indent = len(line) - len(line.lstrip())
        
        if indent > 4:
            # This is the wrong copy - remove it
            # Find the end (next def or end of file)
            next_def = content.find("\ndef ", pos + 10)
            if next_def < 0:
                next_def = len(content)
            
            # Remove the entire function
            content = content[:start] + content[next_def:]
            print(f"Removed copy at indent {indent} (lines starting around {content[:start].count(chr(10))+1})")
            break
    
    # Verify
    count2 = content.count("def place_market_order")
    print(f"After fix: {count2} copies")
    
    with open(path, "w") as f:
        f.write(content)

# Verify the correct one is at indent 4
pos = content.find("def place_market_order")
if pos >= 0:
    start = content.rfind('\n', 0, pos) + 1
    line = content[start:content.find('\n', start)]
    indent = len(line) - len(line.lstrip())
    print(f"Remaining function indent: {indent} (should be 4)")
    
    if indent != 4:
        # Fix indentation
        print("Fixing indentation...")
        lines = content.split('\n')
        # Find the function
        for i, line in enumerate(lines):
            if "def place_market_order" in line:
                base_indent = len(line) - len(line.lstrip())
                shift = 4 - base_indent
                # Shift all lines in this function
                j = i
                while j < len(lines):
                    if lines[j].strip() and j > i and not lines[j].startswith(" ") and lines[j][0].isalpha():
                        break
                    if lines[j].strip():
                        ai = len(lines[j]) - len(lines[j].lstrip())
                        if ai >= base_indent:
                            lines[j] = " " * (ai + shift) + lines[j].lstrip()
                    j += 1
                break
        content = '\n'.join(lines)
        # Clean up empty lines with spaces
        lines2 = []
        for l in content.split('\n'):
            if l.strip():
                lines2.append(l)
            else:
                lines2.append('')
        content = '\n'.join(lines2)
        with open(path, "w") as f:
            f.write(content)
        print(f"Indentation fixed (shifted by {shift})")

import py_compile
try:
    py_compile.compile(path, doraise=True)
    print("SYNTAX: OK")
except Exception as e:
    print(f"SYNTAX ERROR: {e}")
