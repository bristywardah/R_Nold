from rest_framework.permissions import BasePermission

class IsVendorOrAdmin(BasePermission):
    def has_permission(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return request.user.is_authenticated and (
            request.user.is_staff or getattr(request.user, "role", None) == "vendor"
        )
