from django.contrib.auth import get_user_model
from rest_framework import serializers
User=get_user_model()
from backend.apps.accounts.models import Account,SessionRecord
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model=User; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model=Account; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
class SessionRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model=SessionRecord; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
