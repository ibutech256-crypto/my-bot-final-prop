from rest_framework import serializers
from backend.apps.analytics_app.models import PerformanceAnalytics,StrategyStatistic,AIAnalysis
class PerformanceAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model=PerformanceAnalytics; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
class StrategyStatisticSerializer(serializers.ModelSerializer):
    class Meta:
        model=StrategyStatistic; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
class AIAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model=AIAnalysis; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
