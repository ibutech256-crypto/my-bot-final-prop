from decimal import Decimal
from django.conf import settings
from django.db import models
from backend.apps.common.models import BaseModel,Currency
class BrokerProfile(BaseModel): name=models.CharField(max_length=120,db_index=True); broker_type=models.CharField(max_length=50,default="MT5"); server=models.CharField(max_length=160); encrypted_login=models.TextField(); encrypted_password=models.TextField(); is_active=models.BooleanField(default=True,db_index=True)
class BrokerSetting(BaseModel): broker=models.OneToOneField(BrokerProfile,on_delete=models.CASCADE,related_name="settings"); max_retry_count=models.PositiveSmallIntegerField(default=3); order_deviation_points=models.PositiveIntegerField(default=20); heartbeat_seconds=models.PositiveIntegerField(default=15); enable_autotrading=models.BooleanField(default=False)
class TradingAccount(BaseModel):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="trading_accounts"); broker=models.ForeignKey(BrokerProfile,on_delete=models.PROTECT,related_name="trading_accounts"); account_number=models.CharField(max_length=64,db_index=True); account_name=models.CharField(max_length=160); currency=models.CharField(max_length=3,choices=Currency.choices,default=Currency.USD); balance=models.DecimalField(max_digits=18,decimal_places=2,default=Decimal("0.00")); equity=models.DecimalField(max_digits=18,decimal_places=2,default=Decimal("0.00")); margin=models.DecimalField(max_digits=18,decimal_places=2,default=Decimal("0.00")); leverage=models.PositiveIntegerField(default=100); is_live=models.BooleanField(default=False); is_active=models.BooleanField(default=True,db_index=True)
    class Meta: unique_together=("broker","account_number"); indexes=[models.Index(fields=["user","is_active"])]
class TradingSymbol(BaseModel): symbol=models.CharField(max_length=32,unique=True); description=models.CharField(max_length=160,blank=True); asset_class=models.CharField(max_length=40,default="FOREX",db_index=True); digits=models.PositiveSmallIntegerField(default=5); contract_size=models.DecimalField(max_digits=18,decimal_places=4,default=Decimal("100000")); min_lot=models.DecimalField(max_digits=10,decimal_places=2,default=Decimal("0.01")); max_lot=models.DecimalField(max_digits=10,decimal_places=2,default=Decimal("100")); lot_step=models.DecimalField(max_digits=10,decimal_places=2,default=Decimal("0.01")); is_tradeable=models.BooleanField(default=True,db_index=True)
class Watchlist(BaseModel): user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="watchlists"); name=models.CharField(max_length=120); symbols=models.ManyToManyField(TradingSymbol,related_name="watchlists",blank=True)
class SignalDirection(models.TextChoices): BUY="BUY","Buy"; SELL="SELL","Sell"; HOLD="HOLD","Hold"
class SignalStatus(models.TextChoices):
    """Lifecycle states a Signal row can occupy.

    The engine has always written values outside the original five-member set
    (``WATCHLIST``, ``SHADOW_WOULD_EXECUTE``, ``BLOCKED_*``, ``CLOSED_TP`` ...)
    via ``queryset.update()``, which bypasses choice validation. On SQLite the
    24-character ``BLOCKED_RISK_CAP_REACHED`` also silently exceeded the old
    ``max_length=16``. The enumeration and the column width now match what the
    engine actually emits.
    """

    DRAFT = "DRAFT", "Draft"
    NO_SETUP = "NO_SETUP", "No setup"
    WATCHLIST = "WATCHLIST", "Watchlist"
    WAITING_ENTRY = "WAITING_ENTRY", "Waiting for entry"
    ACTIVE = "ACTIVE", "Active"
    SHADOW_WOULD_EXECUTE = "SHADOW_WOULD_EXECUTE", "Shadow - would execute"
    EXECUTED = "EXECUTED", "Executed"
    FILLED = "FILLED", "Filled"
    REJECTED = "REJECTED", "Rejected"
    BLOCKED = "BLOCKED", "Blocked"
    CLOSED_TP = "CLOSED_TP", "Closed at take profit"
    CLOSED_SL = "CLOSED_SL", "Closed at stop loss"
    EXPIRED = "EXPIRED", "Expired"
    CANCELLED = "CANCELLED", "Cancelled"
class Signal(BaseModel):
    """A Romeo TPT setup and its complete decision trail.

    The lifecycle columns added in migration 0002 exist so the dashboard and
    the validation report can answer "why is this still on the watchlist?"
    without grepping the engine log. Every one of them is written by
    ``run_mt5_engine`` on both the create and the refresh path.
    """

    symbol = models.ForeignKey(TradingSymbol, on_delete=models.PROTECT, related_name="signals")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="signals")
    strategy_name = models.CharField(max_length=120, db_index=True)
    direction = models.CharField(max_length=8, choices=SignalDirection.choices)
    status = models.CharField(max_length=32, choices=SignalStatus.choices, default=SignalStatus.ACTIVE, db_index=True)
    entry_price = models.DecimalField(max_digits=18, decimal_places=6)
    stop_loss = models.DecimalField(max_digits=18, decimal_places=6)
    take_profit = models.DecimalField(max_digits=18, decimal_places=6)
    confidence = models.DecimalField(max_digits=5, decimal_places=2)
    rationale = models.TextField()
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # --- Lifecycle / diagnostics (migration 0002) -------------------------- #
    timeframe = models.CharField(max_length=8, blank=True, default="", db_index=True)
    tier = models.CharField(max_length=16, blank=True, default="", db_index=True)
    lifecycle_stage = models.CharField(max_length=32, blank=True, default="", db_index=True)
    #: Machine-readable trading_engine.pipeline_trace.Reason value.
    block_code = models.CharField(max_length=48, blank=True, default="", db_index=True)
    #: Full-sentence explanation. Never a generic string such as "blocked".
    block_reason = models.TextField(blank=True, default="")
    #: ALIGNED / CONFLICT / DATA_UNAVAILABLE / NEUTRAL_ONLY / NOT_EVALUATED.
    htf_status = models.CharField(max_length=24, blank=True, default="", db_index=True)
    #: e.g. "H4=BUY|D1=NEUTRAL".
    htf_detail = models.CharField(max_length=120, blank=True, default="")
    confluences = models.CharField(max_length=255, blank=True, default="")
    spread_pips = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    spread_risk_ratio = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    position_size = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    risk_pct = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    #: JSON-serialised SignalTrace, so the whole funnel path survives a restart.
    lifecycle_json = models.TextField(blank=True, default="")

    class Meta(BaseModel.Meta):
        indexes = [
            models.Index(fields=["symbol", "direction", "status"]),
            models.Index(fields=["status", "created_at"]),
        ]
class Order(BaseModel): account=models.ForeignKey(TradingAccount,on_delete=models.PROTECT,related_name="orders"); signal=models.ForeignKey(Signal,on_delete=models.SET_NULL,null=True,blank=True,related_name="orders"); symbol=models.ForeignKey(TradingSymbol,on_delete=models.PROTECT,related_name="orders"); direction=models.CharField(max_length=8,choices=SignalDirection.choices); order_type=models.CharField(max_length=16,default="MARKET"); status=models.CharField(max_length=16,default="PENDING",db_index=True); requested_volume=models.DecimalField(max_digits=10,decimal_places=2); filled_volume=models.DecimalField(max_digits=10,decimal_places=2,default=Decimal("0.00")); requested_price=models.DecimalField(max_digits=18,decimal_places=6,null=True,blank=True); filled_price=models.DecimalField(max_digits=18,decimal_places=6,null=True,blank=True); stop_loss=models.DecimalField(max_digits=18,decimal_places=6,null=True,blank=True); take_profit=models.DecimalField(max_digits=18,decimal_places=6,null=True,blank=True); broker_ticket=models.CharField(max_length=64,blank=True,db_index=True); rejection_reason=models.TextField(blank=True)
class OpenPosition(BaseModel): account=models.ForeignKey(TradingAccount,on_delete=models.PROTECT,related_name="open_positions"); symbol=models.ForeignKey(TradingSymbol,on_delete=models.PROTECT,related_name="open_positions"); order=models.OneToOneField(Order,on_delete=models.SET_NULL,null=True,blank=True,related_name="position"); direction=models.CharField(max_length=8,choices=SignalDirection.choices); volume=models.DecimalField(max_digits=10,decimal_places=2); entry_price=models.DecimalField(max_digits=18,decimal_places=6); current_price=models.DecimalField(max_digits=18,decimal_places=6); stop_loss=models.DecimalField(max_digits=18,decimal_places=6,null=True,blank=True); take_profit=models.DecimalField(max_digits=18,decimal_places=6,null=True,blank=True); unrealized_profit=models.DecimalField(max_digits=18,decimal_places=2,default=Decimal("0.00")); opened_at=models.DateTimeField(db_index=True); broker_ticket=models.CharField(max_length=64,db_index=True)
class ClosedTrade(BaseModel): account=models.ForeignKey(TradingAccount,on_delete=models.PROTECT,related_name="closed_trades"); symbol=models.ForeignKey(TradingSymbol,on_delete=models.PROTECT,related_name="closed_trades"); direction=models.CharField(max_length=8,choices=SignalDirection.choices); volume=models.DecimalField(max_digits=10,decimal_places=2); entry_price=models.DecimalField(max_digits=18,decimal_places=6); exit_price=models.DecimalField(max_digits=18,decimal_places=6); profit=models.DecimalField(max_digits=18,decimal_places=2); commission=models.DecimalField(max_digits=18,decimal_places=2,default=Decimal("0.00")); swap=models.DecimalField(max_digits=18,decimal_places=2,default=Decimal("0.00")); opened_at=models.DateTimeField(db_index=True); closed_at=models.DateTimeField(db_index=True); broker_ticket=models.CharField(max_length=64,db_index=True)
class TradeJournal(BaseModel): trade=models.OneToOneField(ClosedTrade,on_delete=models.CASCADE,related_name="journal"); user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="trade_journals"); pre_trade_plan=models.TextField(blank=True); post_trade_review=models.TextField(blank=True); emotion=models.CharField(max_length=64,blank=True); mistakes=models.TextField(blank=True); rating=models.PositiveSmallIntegerField(default=0)
