from rest_framework.permissions import BasePermission


class IsOfflineSalesPerson(BasePermission):
    """
    Grants access only to authenticated users with role 'Offline_SalesPerson' or 'SalesPerson'.
    """

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "role", None) in ["Offline_SalesPerson", "SalesPerson"]
        )


class CanViewSalesPersonTracking(BasePermission):
    """
    Grants access to supervisors and administrators who can monitor salespersons:
    SuperAdmin, Distributor, Franchise managers, or superusers.
    """

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        if user.is_superuser:
            return True

        role = getattr(user, "role", None)
        return role in ["SuperAdmin", "Distributor", "Franchise"]


class IsSalesPersonOrSupervisor(BasePermission):
    """
    Grants access to either the salesperson themselves or supervisors/admins.
    """

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        if user.is_superuser:
            return True

        role = getattr(user, "role", None)
        return role in [
            "SuperAdmin",
            "Distributor",
            "Franchise",
            "Offline_SalesPerson",
            "SalesPerson",
        ]
