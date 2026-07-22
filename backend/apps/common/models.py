import uuid
from django.db import models
from django.utils import timezone
class ActiveQuerySet(models.QuerySet):
    def delete(self): return super().update(is_deleted=True,deleted_at=timezone.now())
    def alive(self): return self.filter(is_deleted=False)
class BaseModel(models.Model):
    uuid=models.UUIDField(default=uuid.uuid4,editable=False,unique=True,db_index=True)
    created_at=models.DateTimeField(auto_now_add=True,db_index=True); updated_at=models.DateTimeField(auto_now=True)
    is_deleted=models.BooleanField(default=False,db_index=True); deleted_at=models.DateTimeField(null=True,blank=True)
    objects=ActiveQuerySet.as_manager()
    class Meta: abstract=True; ordering=("-created_at",)
    def soft_delete(self): self.is_deleted=True; self.deleted_at=timezone.now(); self.save(update_fields=["is_deleted","deleted_at","updated_at"])
class Currency(models.TextChoices): USD="USD","US Dollar"; EUR="EUR","Euro"; GBP="GBP","Pound Sterling"; JPY="JPY","Japanese Yen"; UGX="UGX","Uganda Shilling"
