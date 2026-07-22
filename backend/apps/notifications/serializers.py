from rest_framework import serializers
from backend.apps.notifications.models import Notification,TelegramSubscriber
class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model=Notification; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
class TelegramSubscriberSerializer(serializers.ModelSerializer):
    class Meta:
        model=TelegramSubscriber; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
