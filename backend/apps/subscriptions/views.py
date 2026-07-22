from backend.apps.common.viewsets import ActiveModelViewSet
from backend.apps.common.permissions import ReadOnlyOrPrivileged
from backend.apps.subscriptions.models import SubscriptionPlan,Subscription,Invoice,Payment,Refund,Referral
from backend.apps.subscriptions import serializers
class SubscriptionPlanViewSet(ActiveModelViewSet): queryset=SubscriptionPlan.objects.all(); serializer_class=serializers.SubscriptionPlanSerializer; permission_classes=[ReadOnlyOrPrivileged]
class SubscriptionViewSet(ActiveModelViewSet): queryset=Subscription.objects.all(); serializer_class=serializers.SubscriptionSerializer; permission_classes=[ReadOnlyOrPrivileged]
class InvoiceViewSet(ActiveModelViewSet): queryset=Invoice.objects.all(); serializer_class=serializers.InvoiceSerializer; permission_classes=[ReadOnlyOrPrivileged]
class PaymentViewSet(ActiveModelViewSet): queryset=Payment.objects.all(); serializer_class=serializers.PaymentSerializer; permission_classes=[ReadOnlyOrPrivileged]
class RefundViewSet(ActiveModelViewSet): queryset=Refund.objects.all(); serializer_class=serializers.RefundSerializer; permission_classes=[ReadOnlyOrPrivileged]
class ReferralViewSet(ActiveModelViewSet): queryset=Referral.objects.all(); serializer_class=serializers.ReferralSerializer; permission_classes=[ReadOnlyOrPrivileged]
