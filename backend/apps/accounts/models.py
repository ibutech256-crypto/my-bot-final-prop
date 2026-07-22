import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from backend.apps.common.models import BaseModel
class Role(models.TextChoices): ADMIN="ADMIN","Admin"; TRADER="TRADER","Trader"; SUBSCRIBER="SUBSCRIBER","Subscriber"; ANALYST="ANALYST","Analyst"; MODERATOR="MODERATOR","Moderator"; DEVELOPER="DEVELOPER","Developer"; SUPER_ADMIN="SUPER_ADMIN","Super Admin"
class User(AbstractUser):
    uuid=models.UUIDField(default=uuid.uuid4,editable=False,unique=True,db_index=True); role=models.CharField(max_length=32,choices=Role.choices,default=Role.SUBSCRIBER,db_index=True); email=models.EmailField(unique=True,db_index=True); phone=models.CharField(max_length=32,blank=True); email_verified=models.BooleanField(default=False); two_factor_enabled=models.BooleanField(default=False); two_factor_secret_encrypted=models.TextField(blank=True); is_deleted=models.BooleanField(default=False,db_index=True); updated_at=models.DateTimeField(auto_now=True); REQUIRED_FIELDS=["email"]
    class Meta: indexes=[models.Index(fields=["role","is_active"]),models.Index(fields=["email_verified"])]
class Account(BaseModel):
    owner=models.OneToOneField(User,on_delete=models.CASCADE,related_name="account"); display_name=models.CharField(max_length=160); timezone=models.CharField(max_length=64,default="UTC"); risk_disclosure_accepted=models.BooleanField(default=False); marketing_opt_in=models.BooleanField(default=False)
class SessionRecord(BaseModel):
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name="session_records"); ip_address=models.GenericIPAddressField(null=True,blank=True); user_agent=models.TextField(blank=True); refresh_token_jti=models.CharField(max_length=128,db_index=True); revoked_at=models.DateTimeField(null=True,blank=True)
