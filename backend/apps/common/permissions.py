from rest_framework.permissions import BasePermission, SAFE_METHODS
class ReadOnlyOrPrivileged(BasePermission):
    privileged = {"ADMIN", "SUPER_ADMIN", "DEVELOPER", "ANALYST"}
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated and (request.user.is_superuser or getattr(request.user, "role", None) in self.privileged))