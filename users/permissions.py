from rest_framework.permissions import BasePermission
from users.enums import UserRole 


class IsRoleAdmin(BasePermission):
    def has_permission(self, request, view):
        print("User:", request.user, "Role:", getattr(request.user, "role", None))
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", None) == UserRole.ADMIN.value
        )
