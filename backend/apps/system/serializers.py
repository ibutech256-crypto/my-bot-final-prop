from rest_framework import serializers
from backend.apps.system.models import SystemLog,AuditLog,ErrorLog
class SystemLogSerializer(serializers.ModelSerializer):
    class Meta:
        model=SystemLog; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model=AuditLog; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
class ErrorLogSerializer(serializers.ModelSerializer):
    class Meta:
        model=ErrorLog; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
