from backend.apps.common.viewsets import ActiveModelViewSet
from backend.apps.common.permissions import ReadOnlyOrPrivileged
from backend.apps.notifications.models import Notification,TelegramSubscriber
from backend.apps.notifications import serializers
class NotificationViewSet(ActiveModelViewSet): queryset=Notification.objects.all(); serializer_class=serializers.NotificationSerializer; permission_classes=[ReadOnlyOrPrivileged]
class TelegramSubscriberViewSet(ActiveModelViewSet): queryset=TelegramSubscriber.objects.all(); serializer_class=serializers.TelegramSubscriberSerializer; permission_classes=[ReadOnlyOrPrivileged]
