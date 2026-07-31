
content = open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "r").read()
lines = content.split("\n")

# Find the lifecycle block and fix all indentation
for i, line in enumerate(lines):
    if "# v2.2: Lifecycle states based on score tier" in line:
        print(f"Found at line {i+1}")
        
        # Lines to fix - every line from here until status=lifecycle_status
        for j in range(i+1, min(i+15, len(lines))):
            stripped = lines[j].lstrip()
            if not stripped:
                continue
            if "from " in stripped and "import" in stripped:
                break
            if stripped.startswith("status=lifecycle_status"):
                lines[j] = " " * 48 + stripped
                print(f"Line {j+1}: set to indent 48: {stripped[:50]}")
                # Lines below should be at this indent too
                for k in range(j+1, j+10):
                    if k >= len(lines):
                        break
                    ks = lines[k].lstrip()
                    if not ks or ks == ')':
                        continue
                    if "status=" in ks or ")" == stripped:
                        break
                    current_k = len(lines[k]) - len(lines[k].lstrip())
                    if current_k < 48:
                        lines[k] = " " * 48 + ks
                        print(f"Line {k+1}: set to indent 48: {ks[:50]}")
                break
            
            current_indent = len(lines[j]) - len(stripped)
            target_indent = 48  # Base indent for the block
            
            # Lines inside if/elif/else bodies need +4
            if stripped.startswith("lifecycle_status") and "WATCHLIST" in stripped:
                lines[j] = " " * 48 + stripped
                print(f"Line {j+1}: 48: {stripped[:50]}")
            elif stripped.startswith("if ") or stripped.startswith("elif ") or stripped.startswith("else:"):
                lines[j] = " " * 48 + stripped
                print(f"Line {j+1}: 48 (cond): {stripped[:50]}")
            elif stripped.startswith("lifecycle_status") and "EXECUTION_READY" in stripped:
                lines[j] = " " * 52 + stripped
                print(f"Line {j+1}: 52 (body): {stripped[:50]}")
            elif stripped.startswith("lifecycle_status") and ("ACTIVE_MONITORING" in stripped or "WATCHLIST" in stripped):
                lines[j] = " " * 52 + stripped
                print(f"Line {j+1}: 52 (body): {stripped[:50]}")
            else:
                # Try to infer: if previous line ends with :, this is a body
                prev_stripped = lines[j-1].lstrip() if j > 0 else ""
                if prev_stripped.rstrip().endswith(":"):
                    lines[j] = " " * 52 + stripped
                    print(f"Line {j+1}: 52 (after colon): {stripped[:50]}")
                elif current_indent < 48:
                    lines[j] = " " * 48 + stripped
                    print(f"Line {j+1}: 48 (fallback): {stripped[:50]}")
        
        break

# Write back
open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "w").write("\n".join(lines))
print("\nFile saved!")
