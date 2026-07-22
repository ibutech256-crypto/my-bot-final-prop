from backend.apps.common.viewsets import ActiveModelViewSet
from backend.apps.common.permissions import ReadOnlyOrPrivileged
from backend.apps.risk.models import RiskProfile
from backend.apps.risk import serializers
class RiskProfileViewSet(ActiveModelViewSet): queryset=RiskProfile.objects.all(); serializer_class=serializers.RiskProfileSerializer; permission_classes=[ReadOnlyOrPrivileged]
