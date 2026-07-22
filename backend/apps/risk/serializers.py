from rest_framework import serializers
from backend.apps.risk.models import RiskProfile
class RiskProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model=RiskProfile; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
