from backend.apps.common.viewsets import ActiveModelViewSet
from backend.apps.common.permissions import ReadOnlyOrPrivileged
from django.contrib.auth import get_user_model
User=get_user_model()
from backend.apps.accounts.models import Account,SessionRecord
from backend.apps.accounts import serializers
class UserViewSet(ActiveModelViewSet): queryset=User.objects.all(); serializer_class=serializers.UserSerializer; permission_classes=[ReadOnlyOrPrivileged]
class AccountViewSet(ActiveModelViewSet): queryset=Account.objects.all(); serializer_class=serializers.AccountSerializer; permission_classes=[ReadOnlyOrPrivileged]
class SessionRecordViewSet(ActiveModelViewSet): queryset=SessionRecord.objects.all(); serializer_class=serializers.SessionRecordSerializer; permission_classes=[ReadOnlyOrPrivileged]
