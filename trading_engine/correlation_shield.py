
"""Portfolio Correlation Shield - prevents correlated exposure."""
from decimal import Decimal
from backend.apps.trading.models import OpenPosition

CURRENCY_MAP = {
    "EUR": ["EURUSD", "EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURNZD", "EURCAD"],
    "GBP": ["GBPUSD", "GBPJPY", "GBPCHF", "GBPAUD", "GBPNZD", "GBPCAD"],
    "USD": ["USDJPY", "USDCHF", "USDCAD", "EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"],
    "JPY": ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "NZDJPY", "CADJPY", "CHFJPY"],
    "AUD": ["AUDUSD", "AUDJPY", "AUDCHF", "AUDNZD", "AUDCAD"],
    "CHF": ["USDCHF", "EURCHF", "GBPCHF", "AUDCHF", "CHFJPY", "CADCHF"],
    "CAD": ["USDCAD", "EURCAD", "GBPCAD", "AUDCAD", "CADJPY", "CADCHF"],
    "NZD": ["NZDUSD", "NZDJPY", "NZDCAD", "AUDNZD", "GBPNZD"],
}

MAX_CORRELATED = 2  # Max positions per currency direction

def get_currency_exposure(currency, direction):
    """Count open positions involving a specific currency."""
    positions = OpenPosition.objects.filter(is_deleted=False)
    count = 0
    for p in positions:
        sym = p.symbol.symbol.replace("m", "")
        base = sym[:3] if sym[:3] in CURRENCY_MAP else None
        quote = sym[3:6] if len(sym) >= 6 and sym[3:6] in CURRENCY_MAP else None
        if base == currency or quote == currency:
            if p.direction == direction or (quote == currency and p.direction != direction):
                count += 1
    return count

def check_correlation(symbol, direction):
    """Check if adding this trade would exceed correlation limits."""
    sym = symbol.replace("m", "")
    base = sym[:3] if sym[:3] in CURRENCY_MAP else None
    quote = sym[3:6] if len(sym) >= 6 and sym[3:6] in CURRENCY_MAP else None
    
    for currency in [base, quote]:
        if not currency:
            continue
        exposure = get_currency_exposure(currency, direction)
        if exposure >= MAX_CORRELATED:
            return False, f"BLOCKED_CORRELATION: {currency} exposure {exposure}/{MAX_CORRELATED}"
    return True, "PASS Correlation"
