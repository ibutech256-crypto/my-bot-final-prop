from rest_framework import serializers
from backend.apps.subscriptions.models import SubscriptionPlan,Subscription,Invoice,Payment,Refund,Referral
class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model=SubscriptionPlan; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model=Subscription; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model=Invoice; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model=Payment; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
class RefundSerializer(serializers.ModelSerializer):
    class Meta:
        model=Refund; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
class ReferralSerializer(serializers.ModelSerializer):
    class Meta:
        model=Referral; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
