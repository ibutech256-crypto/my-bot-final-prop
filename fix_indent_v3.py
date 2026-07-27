
with open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "r") as f:
    content = f.read()

# Replace the exact malformed block with properly indented version
old_block = """                                                # v2.2: Lifecycle states based on score tier
                                            lifecycle_status = "WATCHLIST"
                                            if score.total >= Decimal("85"):
                                                lifecycle_status = "EXECUTION_READY"  # Priority - skip monitoring
                                            elif score.total >= Decimal("70"):
                                                lifecycle_status = "EXECUTION_READY"
                                            elif score.total >= Decimal("55"):
                                                lifecycle_status = "ACTIVE_MONITORING"
                                            else:
                                            lifecycle_status = "WATCHLIST"
                                            status=lifecycle_status,"""

new_block = """                                                # v2.2: Lifecycle states based on score tier
                                                lifecycle_status = "WATCHLIST"
                                                if score.total >= Decimal("85"):
                                                    lifecycle_status = "EXECUTION_READY"  # Priority - skip monitoring
                                                elif score.total >= Decimal("70"):
                                                    lifecycle_status = "EXECUTION_READY"
                                                elif score.total >= Decimal("55"):
                                                    lifecycle_status = "ACTIVE_MONITORING"
                                                else:
                                                    lifecycle_status = "WATCHLIST"
                                                status=lifecycle_status,"""

if old_block in content:
    content = content.replace(old_block, new_block)
    with open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "w") as f:
        f.write(content)
    print("Fixed lifecycle block indentation!")
    
    # Verify
    import py_compile
    try:
        py_compile.compile(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", doraise=True)
        print("Syntax: OK!")
    except py_compile.PyCompileError as e:
        print(f"Syntax ERROR: {e}")
else:
    print("Could not find old block!")
    # Show what's around line 517
    lines = content.split("\n")
    for i, line in enumerate(lines[515:530], start=516):
        print(f"{i}: {line}")
