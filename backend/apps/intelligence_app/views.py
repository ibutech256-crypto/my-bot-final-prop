from backend.apps.common.viewsets import ActiveModelViewSet
from backend.apps.common.permissions import ReadOnlyOrPrivileged
from backend.apps.intelligence_app import models, serializers
class IntelligenceDecisionLogViewSet(ActiveModelViewSet): queryset=models.IntelligenceDecisionLog.objects.all(); serializer_class=serializers.IntelligenceDecisionLogSerializer; permission_classes=[ReadOnlyOrPrivileged]; filterset_fields=['symbol','module','decision']
class SymbolIntelligenceSnapshotViewSet(ActiveModelViewSet): queryset=models.SymbolIntelligenceSnapshot.objects.all(); serializer_class=serializers.SymbolIntelligenceSnapshotSerializer; permission_classes=[ReadOnlyOrPrivileged]; filterset_fields=['symbol']
class OperationalIncidentViewSet(ActiveModelViewSet): queryset=models.OperationalIncident.objects.all(); serializer_class=serializers.OperationalIncidentSerializer; permission_classes=[ReadOnlyOrPrivileged]; filterset_fields=['component','severity']
class CommercialLicenseRecordViewSet(ActiveModelViewSet): queryset=models.CommercialLicenseRecord.objects.all(); serializer_class=serializers.CommercialLicenseRecordSerializer; permission_classes=[ReadOnlyOrPrivileged]; filterset_fields=['customer_id','plan','active']
