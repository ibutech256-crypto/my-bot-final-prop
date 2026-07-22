from backend.apps.common.viewsets import ActiveModelViewSet
from backend.apps.common.permissions import ReadOnlyOrPrivileged
from backend.apps.analytics_app.models import PerformanceAnalytics,StrategyStatistic,AIAnalysis
from backend.apps.analytics_app import serializers
class PerformanceAnalyticsViewSet(ActiveModelViewSet): queryset=PerformanceAnalytics.objects.all(); serializer_class=serializers.PerformanceAnalyticsSerializer; permission_classes=[ReadOnlyOrPrivileged]
class StrategyStatisticViewSet(ActiveModelViewSet): queryset=StrategyStatistic.objects.all(); serializer_class=serializers.StrategyStatisticSerializer; permission_classes=[ReadOnlyOrPrivileged]
class AIAnalysisViewSet(ActiveModelViewSet): queryset=AIAnalysis.objects.all(); serializer_class=serializers.AIAnalysisSerializer; permission_classes=[ReadOnlyOrPrivileged]
