import os, sys
sys.path.insert(0, "C:/prop-frim-bot")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")
import django; django.setup()
from broker_engine.mt5_client import MT5Client
client = MT5Client(int(os.getenv("MT5_LOGIN")), os.getenv("MT5_PASSWORD"), os.getenv("MT5_SERVER"), os.getenv("MT5_PATH"))
client.connect()
print("MT5 CONNECTED:", client.account_info()["name"], "| Balance:", client.account_info()["balance"])
from trading_engine.broker_intelligence import MT5BrokerIntelligence
bi = MT5BrokerIntelligence(client.mt5)
spec = bi.symbol_spec("ethusdm")
print("ethusdm spec:", spec.symbol, spec.digits, spec.contract_size)
client.shutdown()
