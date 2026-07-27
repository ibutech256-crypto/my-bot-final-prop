
import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, "C:\\prop-frim-bot")
import django
django.setup()
from backend.apps.trading.models import TradingAccount

# Update account name to trigger Growing mode
acct = TradingAccount.objects.first()
if acct:
    print(f"Account: {acct.account_name}, Balance: ${acct.balance}")
    if "GROW" not in acct.account_name.upper():
        acct.account_name = "GROWING Personal Account"
        acct.save()
        print("Account renamed to GROWING Personal Account")
