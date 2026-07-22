from django.conf import settings
from django.db import models
from backend.apps.common.models import BaseModel
class SystemLog(BaseModel): level=models.CharField(max_length=16,db_index=True); source=models.CharField(max_length=64,db_index=True); message=models.TextField(); context=models.JSONField(default=dict)
class AuditLog(BaseModel): actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True); action=models.CharField(max_length=120,db_index=True); resource=models.CharField(max_length=160,db_index=True); resource_uuid=models.UUIDField(null=True,blank=True,db_index=True); ip_address=models.GenericIPAddressField(null=True,blank=True); metadata=models.JSONField(default=dict)
class ErrorLog(BaseModel): source=models.CharField(max_length=64,db_index=True); exception_type=models.CharField(max_length=160); message=models.TextField(); traceback=models.TextField(blank=True); resolved=models.BooleanField(default=False,db_index=True); metadata=models.JSONField(default=dict)
