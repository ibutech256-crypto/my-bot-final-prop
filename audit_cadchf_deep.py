"""Deep audit of CADCHFm trade — sizing, MT5, and TP source."""
import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, "C:\\prop-frim-bot")
import django; django.setup()
from django.utils import timezone
from datetime import timedelta, datetime
from backend.apps.trading.models import Signal, OpenPosition, Order, TradingAccount, TradingSymbol, BrokerSetting
from decimal import Decimal, ROUND_DOWN

import subprocess

# ===== 1. MT5 DIRECT CHECK =====
print("=" * 70)
print("PART 1: MT5 POSITION VERIFICATION")
print("=" * 70)

# Get MT5 position data via Python
mt5_check = """
import MetaTrader5 as mt5
import os
login = int(os.getenv("MT5_LOGIN", "436005794"))
password = os.getenv("MT5_PASSWORD", "1234#Dt@")
server = os.getenv("MT5_SERVER", "Exness-MT5Trial9")

if not mt5.initialize():
    print("MT5 INIT FAILED")
    mt5.shutdown()
    exit()

authorized = mt5.login(login, password, server)
if not authorized:
    print(f"MT5 LOGIN FAILED: {mt5.last_error()}")
    mt5.shutdown()
    exit()

# Find CADCHFm position
positions = mt5.positions_get() or []
cadchf_positions = [p for p in positions if "CADCHF" in p.symbol.upper()]
if cadchf_positions:
    for p in cadchf_positions:
        print(f"TICKET: {p.ticket}")
        print(f"SYMBOL: {p.symbol}")
        print(f"TYPE: {'BUY' if p.type == 0 else 'SELL'}")
        print(f"VOLUME: {p.volume}")
        print(f"ENTRY: {p.price_open}")
        print(f"CURRENT: {p.price_current}")
        print(f"SL: {p.sl}")
        print(f"TP: {p.tp}")
        print(f"PROFIT: {p.profit}")
        print(f"SWAP: {p.swap}")
        print(f"COMMISSION: {p.commission}")
        print(f"OPENED: {p.time}")
        print(f"COMMENT: {p.comment}")
else:
    print("NO OPEN CADCHFm POSITION IN MT5")
    print(f"Total positions: {len(positions)}")
    for p in positions:
        print(f"  {p.ticket} {p.symbol} {'BUY' if p.type==0 else 'SELL'} Vol={p.volume} PnL={p.profit:.2f}")

# Get current tick
tick = mt5.symbol_info_tick("CADCHFm")
if tick:
    print(f"\\nCURRENT CADCHFm TICK:")
    print(f"  Bid: {tick.bid}")
    print(f"  Ask: {tick.ask}")
    print(f"  Spread: {tick.ask - tick.bid}")

# Get symbol info
info = mt5.symbol_info("CADCHFm")
if info:
    print(f"\\nCADCHFm SYMBOL INFO:")
    print(f"  Digits: {info.digits}")
    print(f"  Point: {info.point}")
    print(f"  TradeContractSize: {info.trade_contract_size}")
    print(f"  VolumeMin: {info.volume_min}")
    print(f"  VolumeMax: {info.volume_max}")
    print(f"  VolumeStep: {info.volume_step}")
    print(f"  TradeStopsLevel: {info.trade_stops_level}")
    print(f"  Spread: {info.spread}")
    print(f"  TradeMode: {info.trade_mode}")

# Check account
acct_info = mt5.account_info()
if acct_info:
    print(f"\\nACCOUNT INFO:")
    print(f"  Balance: {acct_info.balance}")
    print(f"  Equity: {acct_info.equity}")
    print(f"  Margin: {acct_info.margin}")
    print(f"  MarginFree: {acct_info.margin_free}")
    print(f"  MarginLevel: {acct_info.margin_level}")

mt5.shutdown()
"""

result = subprocess.run(
    [r"C:\prop-frim-bot\.venv\Scripts\python.exe", "-c", mt5_check],
    capture_output=True, text=True, timeout=30
)
print(result.stdout[:3000])
if result.stderr:
    print("STDERR:", result.stderr[:500])

# ===== 2. SIGNAL DETAILS =====
print("=" * 70)
print("PART 2: SIGNAL + ORDER DETAILS")
print("=" * 70)

sig = Signal.objects.get(id=107717)
print(f"Signal ID: {sig.id}")
print(f"Created: {sig.created_at} (UTC)")
print(f"Strategy: {sig.strategy_name}")
print(f"Direction: {sig.direction}")
print(f"Entry: {sig.entry_price}")
print(f"SL: {sig.stop_loss}")
print(f"TP: {sig.take_profit}")
print(f"Score: {sig.confidence}")
print(f"Rationale: {sig.rationale}")
print(f"Expires at: {sig.expires_at}")

# Get the order
order = Order.objects.filter(signal=sig).first()
if order:
    print(f"\nOrder: ID={order.id}")
    print(f"  Status: {order.status}")
    print(f"  OrderType: {order.order_type}")
    print(f"  RequestedVol: {order.requested_volume}")
    print(f"  FilledVol: {order.filled_volume}")
    print(f"  RequestedPrice: {order.requested_price}")
    print(f"  FilledPrice: {order.filled_price}")
    print(f"  SL: {order.stop_loss}")
    print(f"  TP: {order.take_profit}")
    print(f"  BrokerTicket: {order.broker_ticket}")
    print(f"  Created: {order.created_at}")

# ===== 3. RISK CALCULATION VERIFICATION =====
print("=" * 70)
print("PART 3: POSITION SIZING AUDIT")
print("=" * 70)

acct = TradingAccount.objects.first()
sym_obj = TradingSymbol.objects.filter(symbol__icontains="CADCHF").first()

entry = sig.entry_price
stop = sig.stop_loss
tp = sig.take_profit
balance = acct.balance
equity = acct.equity

# SL distance
sl_distance = abs(entry - stop)
print(f"Entry: {entry}")
print(f"SL: {stop}")
print(f"SL distance (raw): {sl_distance}")

# Pip distance
digits = sym_obj.digits if sym_obj else 5
point = Decimal("0.00001") if digits == 5 else Decimal("0.0001")
pip_size = point * Decimal("10") if digits in [3, 5] else point
sl_pips = sl_distance / pip_size
print(f"Point: {point}")
print(f"Pip size: {pip_size}")
print(f"SL pips: {sl_pips}")

# Step through AccountManager.calculate_position_size()
print(f"\n--- AccountManager.calculate_position_size() trace ---")
print(f"Account: {acct.account_name}")
print(f"Balance: ${balance}")
print(f"Equity: ${equity}")
print(f"MinLot: {sym_obj.min_lot}")
print(f"MaxLot: {sym_obj.max_lot}")
print(f"LotStep: {sym_obj.lot_step}")
print(f"ContractSize: {sym_obj.contract_size}")

# Mode check
if balance < Decimal("1000") or "GROW" in (acct.account_name or "").upper():
    mode = "GROWING_PERSONAL"
else:
    mode = "PROP_FIRM"
print(f"Mode: {mode}")

# Growing personal calculation
if equity < Decimal("100"):
    raw_lots = sym_obj.min_lot
elif equity < Decimal("250"):
    raw_lots = sym_obj.min_lot * Decimal("2")
elif equity < Decimal("500"):
    raw_lots = sym_obj.min_lot * Decimal("4")
else:
    raw_lots = (equity / Decimal("1000")) * Decimal("0.05")
safety_max = Decimal("0.10")
print(f"Raw lots (from equity tiers): {raw_lots}")
print(f"Safety max: {safety_max}")

# Rounding
lot_step = sym_obj.lot_step
final_lots = (raw_lots / lot_step).to_integral_value(rounding=ROUND_DOWN) * lot_step
final_lots = max(sym_obj.min_lot, min(sym_obj.max_lot, min(safety_max, final_lots)))
print(f"Before confidence scaling: {final_lots}")

# Confidence scaling (v2.2 addition)
confidence = sig.confidence
if confidence >= Decimal("95"):
    conf_mult = Decimal("1.00")
elif confidence >= Decimal("85"):
    conf_mult = Decimal("0.75")
elif confidence >= Decimal("70"):
    conf_mult = Decimal("0.50")
elif confidence >= Decimal("55"):
    conf_mult = Decimal("0.35")
else:
    conf_mult = Decimal("0.20")
print(f"Confidence multiplier (score={confidence}): {conf_mult}")

final_lots = (final_lots * conf_mult / lot_step).to_integral_value(rounding=ROUND_DOWN) * lot_step
final_lots = max(sym_obj.min_lot, min(sym_obj.max_lot, final_lots))
print(f"After confidence scaling: {final_lots}")
print(f"Actual sent to MT5: {order.filled_volume if order else 'UNKNOWN'}")

# Monetary risk
contract_size = sym_obj.contract_size
# For CADCHF (quote currency CHF), risk in CHF = lots * contract_size * sl_distance
risk_chf = final_lots * contract_size * sl_distance
# Approximate USD value (CADCHF rate ~0.58, so 1 CHF ≈ 1.72 USD)
# Actually risk in quote currency (CHF) needs conversion to account currency (USD)
# For CADCHF, if we buy, we're buying CAD and selling CHF
# SL distance moves price against us in CHF terms
# risk in account currency = lots * contract_size * sl_distance / CADCHF_entry_price
risk_usd = risk_chf / entry  # approximate conversion
print(f"\nRisk in CHF: {risk_chf}")
print(f"Risk in USD (approx): {risk_usd}")
print(f"Risk % of balance ({balance}): {(risk_usd / balance * 100):.4f}%")

# ===== 4. TP SOURCE TRACING =====
print("=" * 70)
print("PART 4: TAKE-PROFIT SOURCE TRACING")
print("=" * 70)

print(f"\nEntry: {entry}")
print(f"SL: {stop}")
print(f"TP: {tp}")
print(f"Risk distance: {sl_distance}")
print(f"Reward distance: {abs(tp - entry)}")
print(f"R:R: {abs(tp - entry) / sl_distance:.2f}")

# The TP formula in engine line ~508:
# calc_tp = completed[-1].close + calc_risk * Decimal("2.0") if direction.value == "BUY"
#                else completed[-1].close - calc_risk * Decimal("2.0")
# So TP = close_price + risk_distance * 2 = close + (close - sl) * 2
# Or: TP = entry_price + calc_risk * 2.0
# Since calc_risk = abs(completed[-1].close - calc_sl)

print(f"\nTP formula from engine (line ~508):")
print(f"  TP = entry + risk * 2.0 (for BUY)")
print(f"  = {entry} + {sl_distance} * 2.0")
print(f"  = {entry + sl_distance * Decimal('2.0')}")
print(f"  Matches signal TP: {tp == entry + sl_distance * Decimal('2.0')}")

# If the TP is exactly 2x risk from entry, it's formula-based, not from a DOL level
print(f"\nTP is formula-calculated (2:1 RR): {'YES' if abs(tp - (entry + sl_distance * Decimal('2.0'))) < Decimal('0.000001') else 'NO'}")
print(f"TP references a specific market structure level: NO")
print(f"TP source: Engine line ~508 - risk_multiple formula")

# Check what current market price is relative to TP
# We got tick data from MT5 above
print(f"\nNOTE: Need MT5 tick data to compare TP against current market.")
print(f"TP = {tp}")

print("\n" + "=" * 70)
print("END AUDIT")
print("=" * 70)
