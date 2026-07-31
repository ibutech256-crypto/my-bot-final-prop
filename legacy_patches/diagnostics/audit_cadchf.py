"""Audit the CADCHFm autonomous trade - sizing and TP."""
import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, "C:\\prop-frim-bot")
import django; django.setup()
from django.utils import timezone
from datetime import timedelta
from backend.apps.trading.models import Signal, OpenPosition, Order, TradingAccount, TradingSymbol, BrokerSetting
from decimal import Decimal, ROUND_DOWN
import json

# ===== 1. FIND THE CADCHFm POSITION =====
print("=" * 60)
print("CADCHFm AUTONOMOUS TRADE AUDIT")
print("=" * 60)

# Check OpenPosition
pos = OpenPosition.objects.filter(symbol__symbol__icontains="CADCHF", is_deleted=False).order_by("-created_at").first()
if pos:
    print(f"\n=== OPEN POSITION (DB) ===")
    print(f"Symbol: {pos.symbol.symbol}")
    print(f"Direction: {pos.direction}")
    print(f"Volume: {pos.volume}")
    print(f"Entry: {pos.entry_price}")
    print(f"Current: {pos.current_price}")
    print(f"SL: {pos.stop_loss}")
    print(f"TP: {pos.take_profit}")
    print(f"Unrealized PnL: {pos.unrealized_profit}")
    print(f"Broker Ticket: {pos.broker_ticket}")
    print(f"Opened: {pos.opened_at}")
    if pos.order:
        print(f"Order ID: {pos.order.id}")
else:
    print("No open position found for CADCHFm")

# Check Orders for CADCHFm
orders = Order.objects.filter(symbol__symbol__icontains="CADCHF").order_by("-created_at")[:3]
print(f"\n=== ORDERS ===")
for o in orders:
    print(f"ID={o.id} Type={o.order_type} Status={o.status} RequestedVol={o.requested_volume} FilledVol={o.filled_volume}")
    print(f"  RequestedPrice={o.requested_price} FilledPrice={o.filled_price}")
    print(f"  SL={o.stop_loss} TP={o.take_profit}")
    print(f"  BrokerTicket={o.broker_ticket} Rejection={o.rejection_reason}")
    if o.signal:
        print(f"  SignalID={o.signal.id}")

# Find the Signal that led to this trade
if pos and pos.order and pos.order.signal:
    sig = pos.order.signal
else:
    # Search by symbol
    sig = Signal.objects.filter(symbol__symbol__icontains="CADCHF").order_by("-created_at").first()

if sig:
    print(f"\n=== SIGNAL ===")
    print(f"Signal ID: {sig.id}")
    print(f"Symbol: {sig.symbol.symbol}")
    print(f"Direction: {sig.direction}")
    print(f"Score: {sig.confidence}")
    print(f"Status: {sig.status}")
    print(f"Entry: {sig.entry_price}")
    print(f"SL: {sig.stop_loss}")
    print(f"TP: {sig.take_profit}")
    print(f"Strategy: {sig.strategy_name}")
    print(f"Rationale: {sig.rationale}")
    print(f"Created: {sig.created_at}")
    print(f"Symbol tradeable: {sig.symbol.is_tradeable}")

# ===== 2. ACCOUNT INFO =====
print(f"\n=== ACCOUNT ===")
acct = TradingAccount.objects.first()
if acct:
    print(f"Account: {acct.account_name}")
    print(f"Balance: ${acct.balance}")
    print(f"Equity: ${acct.equity}")
    print(f"Currency: {acct.currency}")

# ===== 3. BROKER SETTINGS =====
bs = BrokerSetting.objects.first()
if bs:
    print(f"\n=== BROKER SETTINGS ===")
    print(f"Auto-trading: {bs.enable_autotrading}")
    print(f"Deviation: {bs.order_deviation_points}")

# ===== 4. SYMBOL INFO =====
sym_obj = TradingSymbol.objects.filter(symbol__icontains="CADCHF").first()
if sym_obj:
    print(f"\n=== SYMBOL DEFINITION ===")
    print(f"Symbol: {sym_obj.symbol}")
    print(f"Class: {sym_obj.asset_class}")
    print(f"Digits: {sym_obj.digits}")
    print(f"ContractSize: {sym_obj.contract_size}")
    print(f"MinLot: {sym_obj.min_lot}")
    print(f"MaxLot: {sym_obj.max_lot}")
    print(f"LotStep: {sym_obj.lot_step}")

# ===== 5. CALCULATE RISK =====
if sig and pos:
    print(f"\n=== RISK CALCULATION ===")
    entry = sig.entry_price
    stop = sig.stop_loss
    balance = acct.balance if acct else Decimal("0")
    
    # SL distance in price
    sl_distance = abs(entry - stop)
    print(f"Entry: {entry}")
    print(f"SL: {stop}")
    print(f"SL distance (price): {sl_distance}")
    
    # Pips for CADCHF (4 decimals, typically)
    # CADCHF is usually quoted to 5 digits, pip is 0.0001
    if sym_obj:
        point = Decimal("0.00001") if sym_obj.digits == 5 else Decimal("0.0001")
        pip_size = point * Decimal("10") if sym_obj.digits in [3, 5] else point
        sl_pips = sl_distance / pip_size
        print(f"Point: {point}")
        print(f"Pip size: {pip_size}")
        print(f"SL distance (pips): {sl_pips}")
    
    # Contract value
    contract_size = sym_obj.contract_size if sym_obj else Decimal("100000")
    print(f"\nContract size: {contract_size}")
    
    # Risk in USD for 0.01 lot
    lot = pos.volume
    risk_usd = lot * contract_size * sl_distance
    # For forex, risk = lots * contract_size * sl_in_price_terms
    # But need to convert to account currency
    print(f"\nActual lot sent: {lot}")
    print(f"Risk in quote currency (CHF): {risk_usd}")
    
    # Risk percentage
    risk_pct = (risk_usd / balance * Decimal("100")) if balance > 0 else Decimal("0")
    print(f"Risk percentage: {risk_pct:.4f}%")
    print(f"Account balance: ${balance}")
    
    # What the AccountManager should have calculated
    print(f"\n=== EXPECTED CALCULATION (per code) ===")
    print(f"Mode: Growing Personal (balance ${balance})")
    equity = acct.equity if acct else Decimal("0")
    print(f"Equity: ${equity}")
    
    # From account_manager.py calculate_position_size:
    # if equity < 100: raw = min_lot
    # elif equity < 250: raw = min_lot * 2
    # elif equity < 500: raw = min_lot * 4
    # else: raw = (equity / 1000) * 0.05
    min_lot = sym_obj.min_lot if sym_obj else Decimal("0.01")
    if equity < Decimal("100"):
        raw = min_lot
    elif equity < Decimal("250"):
        raw = min_lot * 2
    elif equity < Decimal("500"):
        raw = min_lot * 4
    else:
        raw = (equity / Decimal("1000")) * Decimal("0.05")
    safety_max = Decimal("0.10")
    print(f"Raw lot from equity: {raw}")
    print(f"Safety max: {safety_max}")
    calculated = min(raw, safety_max)
    print(f"Pre-rounding: {calculated}")
    
    # AccountManager rounds: (raw / lot_step).to_integral_value(ROUND_DOWN) * lot_step
    lot_step = sym_obj.lot_step if sym_obj else Decimal("0.01")
    final_lots = (calculated / lot_step).to_integral_value(rounding=ROUND_DOWN) * lot_step
    final_lots = max(min_lot, min(sym_obj.max_lot if sym_obj else Decimal("100"), min(safety_max, final_lots)))
    print(f"Final calculated lot: {final_lots}")
    print(f"Actual lot sent: {lot}")
    print(f"Match: {final_lots == lot}")

# ===== 6. TP ANALYSIS =====
if sig:
    print(f"\n=== TP ANALYSIS ===")
    print(f"Entry: {sig.entry_price}")
    print(f"SL: {sig.stop_loss}")
    print(f"TP: {sig.take_profit}")
    
    # Risk:Reward
    risk = abs(sig.entry_price - sig.stop_loss)
    reward = abs(sig.take_profit - sig.entry_price)
    rr = reward / risk if risk > 0 else Decimal("0")
    print(f"Risk: {risk}")
    print(f"Reward: {reward}")
    print(f"R:R Ratio: {rr:.2f}")
    
    # Check if TP is on the correct side
    if sig.direction == "BUY":
        tp_above_entry = sig.take_profit > sig.entry_price
        sl_below_entry = sig.stop_loss < sig.entry_price
    else:
        tp_above_entry = sig.take_profit < sig.entry_price
        sl_below_entry = sig.stop_loss > sig.entry_price
    print(f"TP on correct side: {tp_above_entry}")
    print(f"SL on correct side: {sl_below_entry}")

print("\n" + "=" * 60)
print("END AUDIT")
print("=" * 60)
