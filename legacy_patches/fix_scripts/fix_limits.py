"""Fix account manager limits."""
content = open(r"C:\prop-frim-bot\trading_engine\account_manager.py", "r").read()
content = content.replace("max_open_positions = 4", "max_open_positions = 10")
content = content.replace("max_daily_trades = 15", "max_daily_trades = 50")
content = content.replace("daily_target_trades = 10", "daily_target_trades = 25")
open(r"C:\prop-frim-bot\trading_engine\account_manager.py", "w").write(content)
print("Limits updated: 4->10, 15->50, 10->25")
