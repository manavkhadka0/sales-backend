from rest_framework.permissions import BasePermission


class IsSuperAdmin(BasePermission):
    """
    Grants access only to SuperAdmin users (or Django superusers).
    Used to protect attendance config and access management endpoints.
    """

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return user.is_superuser or getattr(user, "role", None) == "SuperAdmin"


class HasOfflineSalesAccess(BasePermission):
    """
    Grants read access to offline sales data only to SuperAdmin users
    who are explicitly whitelisted in OfflineSalesAccess.
    Django superusers bypass the whitelist check.
    """

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser:
            return True
        if getattr(user, "role", None) != "SuperAdmin":
            return False
        # Lazy import to avoid circular dependency
        from offlineSales.models import OfflineSalesAccess
        return OfflineSalesAccess.objects.filter(user=user).exists()


class CanPostAttendance(BasePermission):
    """
    Grants attendance-posting access to Offline_SalesPerson / SalesPerson roles.
    """

    ALLOWED_ROLES = ["Offline_SalesPerson", "SalesPerson"]

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "role", None) in self.ALLOWED_ROLES
        )


class CanViewAttendance(BasePermission):
    """
    Supervisors can view all attendance; salespersons can only view their own.
    The queryset is scoped in the selector — this permission just ensures
    the user is authenticated.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
