from django.conf import settings
from django.db import models
from backend.apps.common.models import BaseModel
class IntelligenceDecisionLog(BaseModel):
    symbol=models.CharField(max_length=64,db_index=True); module=models.CharField(max_length=120,db_index=True); decision=models.CharField(max_length=64,db_index=True); score_before=models.DecimalField(max_digits=8,decimal_places=2,null=True,blank=True); score_after=models.DecimalField(max_digits=8,decimal_places=2,null=True,blank=True); reasons=models.JSONField(default=list); reversible=models.BooleanField(default=True); approved_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True)
class SymbolIntelligenceSnapshot(BaseModel):
    symbol=models.CharField(max_length=64,db_index=True); metrics=models.JSONField(default=dict); confidence_score=models.DecimalField(max_digits=8,decimal_places=2,default=0)
class OperationalIncident(BaseModel):
    component=models.CharField(max_length=120,db_index=True); severity=models.CharField(max_length=32,db_index=True); message=models.TextField(); metadata=models.JSONField(default=dict); resolved_at=models.DateTimeField(null=True,blank=True)
class CommercialLicenseRecord(BaseModel):
    customer_id=models.CharField(max_length=120,db_index=True); license_key_hash=models.CharField(max_length=128,db_index=True); plan=models.CharField(max_length=64); machine_hash=models.CharField(max_length=128,blank=True); features=models.JSONField(default=dict); expires_at=models.DateTimeField(db_index=True); active=models.BooleanField(default=True)
