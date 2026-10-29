from decimal import Decimal

from django.db.models import (
    Count,
    DecimalField,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce, Greatest

from offlineSales.models import OfflineCustomer, OfflineOrder, OfflinePaymentHistory


def get_customer_queryset(user):
    """
    Returns optimized customer queryset with aggregated sales and credit metrics:
    - total_orders_count
    - total_purchased_amount
    - total_paid_amount (calculated across direct customer payments AND order payments)
    - total_remaining_amount (outstanding credit balance: max(0, total_purchased - total_paid))

    Regular 'SalesPerson' is restricted and will NOT receive offline sales data.
    'Offline_SalesPerson' receives only their own customers (sales_person=user).
    'Franchise' receives customers scoped to their franchise.
    'SuperAdmin' receives all customers.
    """
    if not user or not user.is_authenticated:
        return OfflineCustomer.objects.none()

    user_role = getattr(user, "role", None)

    orders_count_subquery = Subquery(
        OfflineOrder.objects.filter(
            customer_id=OuterRef("pk")
        )
        .exclude(order_status=OfflineOrder.OrderStatus.CANCELLED)
        .annotate(dummy=Value(1))
        .values("dummy")
        .annotate(total=Count("id"))
        .values("total")[:1],
        output_field=IntegerField(),
    )

    purchased_subquery = Subquery(
        OfflineOrder.objects.filter(
            customer_id=OuterRef("pk")
        )
        .exclude(order_status=OfflineOrder.OrderStatus.CANCELLED)
        .annotate(dummy=Value(1))
        .values("dummy")
        .annotate(total=Sum("total_amount"))
        .values("total")[:1],
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )

    payment_subquery = Subquery(
        OfflinePaymentHistory.objects.filter(
            Q(customer_id=OuterRef("pk")) | Q(order__customer_id=OuterRef("pk"))
        )
        .exclude(order__order_status=OfflineOrder.OrderStatus.CANCELLED)
        .annotate(dummy=Value(1))
        .values("dummy")
        .annotate(total=Sum("amount"))
        .values("total")[:1],
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )

    zero_decimal = Value(
        Decimal("0.00"), output_field=DecimalField(max_digits=12, decimal_places=2)
    )

    qs = (
        OfflineCustomer.objects
        .select_related("franchise", "sales_person")
        .annotate(
            annotated_total_orders=Coalesce(
                orders_count_subquery, Value(0, output_field=IntegerField())
            ),
            annotated_total_purchased=Coalesce(purchased_subquery, zero_decimal),
            annotated_total_paid=Coalesce(payment_subquery, zero_decimal),
        )
        .annotate(
            annotated_total_remaining=Greatest(
                zero_decimal,
                F("annotated_total_purchased") - F("annotated_total_paid"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
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


def get_customer_detail(customer_id: int, user):
    """Fetch single customer by ID scoped to user."""
    return get_customer_queryset(user).filter(id=customer_id).first()
