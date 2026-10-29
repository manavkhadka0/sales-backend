from datetime import timedelta

from django.utils import timezone

from offlineSales.models import OfflineOrder


def get_order_queryset(user):
    """
    Returns optimized offline orders queryset with related franchise,
    sales_person, customer, items, and payment history.

    Regular 'SalesPerson' is restricted and will NOT receive offline sales data.
    'Offline_SalesPerson' receives only their own orders (sales_person=user).
    'Franchise' receives orders scoped to their franchise.
    'SuperAdmin' receives all offline orders.
    """
    if not user or not user.is_authenticated:
        return OfflineOrder.objects.none()

    user_role = getattr(user, "role", None)

    qs = (
        OfflineOrder.objects
        .select_related("franchise", "sales_person", "customer")
        .prefetch_related(
            "items",
            "items__inventory",
            "items__inventory__product",
            "payment_history",
            "payment_history__recorded_by",
        )
    )

    if user_role == "SuperAdmin":
        return qs.all()
    elif user_role == "Franchise" and hasattr(user, "franchise") and user.franchise:
        return qs.filter(franchise=user.franchise)
    elif user_role == "Offline_SalesPerson":
        if hasattr(user, "franchise") and user.franchise:
            return qs.filter(sales_person=user, franchise=user.franchise)
        return qs.filter(sales_person=user)
    elif hasattr(user, "franchise") and user.franchise:
        return qs.filter(franchise=user.franchise)

    return qs.none()


def get_customer_orders(customer_id: int, user):
    """Returns order history for a specific customer."""
    return get_order_queryset(user).filter(customer_id=customer_id)


def get_pending_credit_reminders(user, days_threshold=60):
    """
    Returns non-cancelled orders with pending credit (remaining_amount > 0)
    that are close to or exceeding the 3-month (90 days) credit window.
    Default threshold: orders older than 60 days.
    Ordered by order_date ascending (oldest/most urgent first).
    """
    today = timezone.localdate()
    cutoff_date = today - timedelta(days=days_threshold)

    return (
        get_order_queryset(user)
        .exclude(order_status=OfflineOrder.OrderStatus.CANCELLED)
        .filter(
            remaining_amount__gt=0,
            order_date__lte=cutoff_date,
        )
        .order_by("order_date")
    )
