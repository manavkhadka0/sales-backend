from rest_framework.permissions import BasePermission


class IsSuperAdmin(BasePermission):
    """
    Grants access only to SuperAdmin users or Django superusers.
    """

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return bool(user.is_superuser or getattr(user, "role", None) == "SuperAdmin")
