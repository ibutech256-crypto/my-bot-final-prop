from backend.apps.common.viewsets import ActiveModelViewSet
from backend.apps.common.permissions import ReadOnlyOrPrivileged
from backend.apps.system.models import SystemLog,AuditLog,ErrorLog
from backend.apps.system import serializers
class SystemLogViewSet(ActiveModelViewSet): queryset=SystemLog.objects.all(); serializer_class=serializers.SystemLogSerializer; permission_classes=[ReadOnlyOrPrivileged]
class AuditLogViewSet(ActiveModelViewSet): queryset=AuditLog.objects.all(); serializer_class=serializers.AuditLogSerializer; permission_classes=[ReadOnlyOrPrivileged]
class ErrorLogViewSet(ActiveModelViewSet): queryset=ErrorLog.objects.all(); serializer_class=serializers.ErrorLogSerializer; permission_classes=[ReadOnlyOrPrivileged]
