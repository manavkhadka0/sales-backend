from django.db.models import Q

from offlineSales.models import OfflinePaymentHistory


def get_payment_queryset(user):
    """
    Returns optimized payment history queryset with related order, customer,
    franchise, and recorded_by user.

    Regular 'SalesPerson' is restricted and will NOT receive offline payment data.
    'Offline_SalesPerson' receives payment records scoped to their own orders or recorded by them.
    'Franchise' receives payment records scoped to their franchise.
    'SuperAdmin' receives all records.
    """
    if not user or not user.is_authenticated:
        return OfflinePaymentHistory.objects.none()

    user_role = getattr(user, "role", None)

    qs = OfflinePaymentHistory.objects.select_related(
        "customer",
        "customer__franchise",
        "order",
        "order__customer",
        "order__franchise",
        "recorded_by",
    )

    if user_role == "SuperAdmin":
        return qs.all()
    elif user_role == "Franchise" and hasattr(user, "franchise") and user.franchise:
        return qs.filter(
            Q(order__franchise=user.franchise) | Q(customer__franchise=user.franchise)
        )
    elif user_role == "Offline_SalesPerson":
        own_filter = (
            Q(recorded_by=user)
            | Q(order__sales_person=user)
            | Q(customer__sales_person=user)
        )
        if hasattr(user, "franchise") and user.franchise:
            franchise_filter = (
                Q(order__franchise=user.franchise) | Q(customer__franchise=user.franchise)
            )
            return qs.filter(own_filter).filter(franchise_filter)
        return qs.filter(own_filter)
    elif hasattr(user, "franchise") and user.franchise:
        return qs.filter(
            Q(order__franchise=user.franchise) | Q(customer__franchise=user.franchise)
        )

    return qs.none()
