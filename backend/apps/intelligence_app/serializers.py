from rest_framework import serializers
from backend.apps.intelligence_app import models
class IntelligenceDecisionLogSerializer(serializers.ModelSerializer):
    class Meta: model=models.IntelligenceDecisionLog; fields='__all__'; read_only_fields=('uuid','created_at','updated_at')
class SymbolIntelligenceSnapshotSerializer(serializers.ModelSerializer):
    class Meta: model=models.SymbolIntelligenceSnapshot; fields='__all__'; read_only_fields=('uuid','created_at','updated_at')
class OperationalIncidentSerializer(serializers.ModelSerializer):
    class Meta: model=models.OperationalIncident; fields='__all__'; read_only_fields=('uuid','created_at','updated_at')
class CommercialLicenseRecordSerializer(serializers.ModelSerializer):
    class Meta: model=models.CommercialLicenseRecord; fields='__all__'; read_only_fields=('uuid','created_at','updated_at')
