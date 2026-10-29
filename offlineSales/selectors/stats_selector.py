from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from offlineSales.models import OfflineOrder
from offlineSales.selectors.customer_selector import get_customer_queryset
from offlineSales.selectors.order_selector import get_order_queryset
from offlineSales.selectors.payment_selector import get_payment_queryset


def get_offline_sales_stats(user):
    """
    Computes overall statistics:
    - total_customers
    - customers_with_pending_credit
    - total_orders
    - pending_orders_count
    - close_to_due_orders_count (60 to 89 days old with pending credit)
    - overdue_orders_count (>= 90 days old with pending credit)
    - total_order_amount
    - total_paid_amount
    - total_remaining_amount
    Scoped to user's permissions and franchise.
    If user is 'Offline_SalesPerson', aggregates are strictly isolated to their own data.
    """
    customer_qs = get_customer_queryset(user)
    order_qs = get_order_queryset(user).exclude(
        order_status=OfflineOrder.OrderStatus.CANCELLED
    )

    user_role = getattr(user, "role", None)
    if user_role == "Offline_SalesPerson":
        customer_qs = customer_qs.filter(sales_person=user)
        order_qs = order_qs.filter(sales_person=user)

    today = timezone.localdate()
    sixty_days_ago = today - timedelta(days=60)
    ninety_days_ago = today - timedelta(days=90)

    # Customer aggregates
    total_customers = customer_qs.filter(is_active=True).count()
    customers_with_pending_credit = customer_qs.filter(
        is_active=True,
        annotated_total_remaining__gt=0,
    ).count()

    # Order aggregates in single query
    order_aggregates = order_qs.order_by().aggregate(
        total_orders=Count("id"),
        pending_orders_count=Count("id", filter=Q(remaining_amount__gt=0)),
        close_to_due_orders_count=Count(
            "id",
            filter=Q(
                remaining_amount__gt=0,
                order_date__lte=sixty_days_ago,
                order_date__gt=ninety_days_ago,
            ),
        ),
        overdue_orders_count=Count(
            "id",
            filter=Q(
                remaining_amount__gt=0,
                order_date__lte=ninety_days_ago,
            ),
        ),
        total_order_amount=Coalesce(
            Sum("total_amount"),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        ),
    )

    # Total payments recorded across both order payments and direct customer payments
    payment_qs = get_payment_queryset(user).exclude(
        order__order_status=OfflineOrder.OrderStatus.CANCELLED
    )
    total_paid_amount = payment_qs.order_by().aggregate(
        total=Coalesce(
            Sum("amount"),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )
    )["total"]

    total_order_amount = order_aggregates["total_order_amount"]
    total_remaining_amount = max(Decimal("0.00"), total_order_amount - total_paid_amount)

    return {
        "total_customers": total_customers,
        "customers_with_pending_credit": customers_with_pending_credit,
        "total_orders": order_aggregates["total_orders"],
        "pending_orders_count": order_aggregates["pending_orders_count"],
        "close_to_due_orders_count": order_aggregates["close_to_due_orders_count"],
        "overdue_orders_count": order_aggregates["overdue_orders_count"],
        "total_order_amount": total_order_amount,
        "total_paid_amount": total_paid_amount,
        "total_remaining_amount": total_remaining_amount,
    }
