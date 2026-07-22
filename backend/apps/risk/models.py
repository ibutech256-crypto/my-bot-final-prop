from decimal import Decimal
from django.conf import settings
from django.db import models
from backend.apps.common.models import BaseModel
class RiskProfile(BaseModel):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="risk_profiles"); name=models.CharField(max_length=120); max_risk_per_trade_pct=models.DecimalField(max_digits=5,decimal_places=2,default=Decimal("1.00")); max_daily_loss_pct=models.DecimalField(max_digits=5,decimal_places=2,default=Decimal("3.00")); max_total_drawdown_pct=models.DecimalField(max_digits=5,decimal_places=2,default=Decimal("10.00")); max_open_positions=models.PositiveIntegerField(default=5); max_correlation_exposure=models.DecimalField(max_digits=5,decimal_places=2,default=Decimal("30.00")); enforce_stop_loss=models.BooleanField(default=True); is_default=models.BooleanField(default=False)
    class Meta: unique_together=("user","name"); indexes=[models.Index(fields=["user","is_default"])]
