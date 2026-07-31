"""Check engine file syntax."""
import py_compile, sys
try:
    py_compile.compile(
        r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py",
        doraise=True
    )
    print("SYNTAX OK")
except py_compile.PyCompileError as e:
    print(f"SYNTAX ERROR: {e}")
except Exception as e:
    print(f"OTHER ERROR: {e}")
