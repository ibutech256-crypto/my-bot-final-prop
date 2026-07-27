"""Check how many ACTIVE_SYMBOLS are available in MT5."""
import MetaTrader5 as mt5
import os

login = int(os.getenv("MT5_LOGIN", "436005794"))
pw = os.getenv("MT5_PASSWORD", "1234#Dt@")
sv = os.getenv("MT5_SERVER", "Exness-MT5Trial9")

mt5.initialize()
mt5.login(login, pw, sv)

symbols = mt5.symbols_get() or []
mt5_names = set(s.name for s in symbols)
print(f"Total MT5 symbols: {len(mt5_names)}")

# Our active symbols
actives = [
    "EURUSDm","GBPUSDm","USDJPYm","AUDUSDm","USDCADm","NZDUSDm","USDCHFm",
    "EURGBPm","EURAUDm","EURCADm","EURNZDm","EURCHFm","EURJPYm",
    "GBPAUDm","GBPCADm","GBPNZDm","GBPCHFm","GBPJPYm",
    "AUDCADm","AUDNZDm","AUDCHFm","AUDJPYm",
    "NZDCADm","NZDCHFm","NZDJPYm","CADCHFm","CADJPYm","CHFJPYm",
    "EURSGDm","GBPSGDm","AUDSGDm","NZDSGDm","CADSGDm","USDSGDm",
    "EURNOKm","USDNOKm","EURSEKm","USDSEKm","USDDKKm","EURDKKm",
    "EURPLNm","USDPLNm","EURHUFm","USDHUFm",
    "AUDNOKm","NZDNOKm","AUDSEKm","NZDSEKm","ZARJPYm",
    "USDZARm","EURZARm","GBPZARm","USDMXNm","EURMXNm",
    "USDTRYm","EURTRYm","USDCNHm","USDHKDm","USDSGDm",
    "USDTHBm","USDPLNm","USDHUFm","USDSEKm","USDNOKm","USDDKKm",
    "XAUUSDm","XAGUSDm","XPTUSDm","XPDUSDm","XAUEURm","XAGEURm",
    "USOILm","UKOILm","NGASm","COPPERm",
    "US30m","SPX500m","NAS100m","GER40m","UK100m",
    "FRA40m","JP225m","AUS200m","EU50m","ES35m",
    "IT40m","HK50m","SG30m","CN50m","US2000m",
    "BTCUSDm","ETHUSDm","LTCUSDm","XRPUSDm","BCHUSDm",
    "ADAUSDm","SOLUSDm","DOTUSDm","LINKUSDm",
    "MATICUSDm","UNIUSDm","XLMUSDm","ALGOUSDm","NEARUSDm",
    "ATOMUSDm","ETCUSDm","ICPUSDm","FILUSDm",
    "VETUSDm","SANDUSDm","MANAUSDm","AXSUSDm",
]

found = 0
missing = []
for a in actives:
    if a in mt5_names:
        found += 1
    else:
        missing.append(a)

print(f"\nIn ACTIVE list: {len(actives)}")
print(f"Found in MT5: {found}")
print(f"Missing: {len(missing)}")
for m in missing:
    # Try without 'm' suffix
    without_m = m.replace("m", "")
    if without_m in mt5_names:
        print(f"  {m} -> available as {without_m}")
    else:
        print(f"  {m} -> NOT AVAILABLE in any form")

mt5.shutdown()
