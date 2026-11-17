from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from django.db.models import Prefetch, Q, QuerySet
from django.utils import timezone

from export_data.filters import BulkOilOrderFilter
from export_data.utils import is_oil_bottle
from sales.models import Order, OrderProduct

DEFAULT_START_DATE = date(2026, 10, 4)
DEFAULT_END_DATE = date(2026, 11, 16)
DEFAULT_MIN_OIL_BOTTLES = 3


def get_bulk_oil_orders_base_queryset() -> QuerySet:
    """
    Returns an optimized base queryset for orders.
    Eagerly loads location, franchise, and sales_person,
    and prefetches order_products with nested product relationships
    to prevent N+1 query overhead.
    """
    return (
        Order.objects.select_related("location", "franchise", "sales_person")
        .prefetch_related(
            Prefetch(
                "order_products",
                queryset=OrderProduct.objects.select_related("product__product"),
            )
        )
        .order_by("-date", "-created_at", "-id")
    )


def _parse_date(date_val: Any, default: date) -> date:
    """Helper to parse string or date object safely into datetime.date."""
    if not date_val:
        return default
    if isinstance(date_val, date) and not isinstance(date_val, datetime):
        return date_val
    if isinstance(date_val, datetime):
        return date_val.date()
    try:
        return datetime.strptime(str(date_val).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return default


def get_bulk_oil_orders(
    params: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Order], date, date]:
    """
    Queries and returns orders meeting the bulk oil bottle criteria:
    - Order date or created_at falls between start_date and end_date (default: 2026-10-04 to 2026-11-16).
    - Contains >= min_oil_bottles (default: 3) oil bottles across order items.
    - Each qualifying order is enriched with pre-formatted display attributes.
    """
    data = params.copy() if params else {}

    raw_start = data.get("start_date") or data.get("date_from")
    raw_end = data.get("end_date") or data.get("date_to")

    start_date = _parse_date(raw_start, DEFAULT_START_DATE)
    end_date = _parse_date(raw_end, DEFAULT_END_DATE)

    raw_min_qty = data.get("min_oil_bottles") or data.get("min_quantity")
    try:
        min_oil_bottles = int(raw_min_qty) if raw_min_qty is not None else DEFAULT_MIN_OIL_BOTTLES
    except (ValueError, TypeError):
        min_oil_bottles = DEFAULT_MIN_OIL_BOTTLES

    # Start with optimized base queryset
    qs = get_bulk_oil_orders_base_queryset()

    # Pre-filter candidate orders by keywords at the database level for performance
    qs = qs.filter(
        Q(order_products__product__product__name__icontains="oil")
        | Q(order_products__product__product__name__icontains="bottle")
        | Q(order_products__product__product__name__icontains="baldness")
        | Q(order_products__product__product__name__icontains="hairfall")
        | Q(order_products__product__product__name__icontains="dandruff")
        | Q(order_products__product__product__name__icontains="yachu")
    ).distinct()

    # Apply date boundaries if not explicitly parsed by FilterSet
    if not raw_start:
        qs = qs.filter(Q(created_at__date__gte=start_date) | Q(date__gte=start_date))
    if not raw_end:
        qs = qs.filter(Q(created_at__date__lte=end_date) | Q(date__lte=end_date))

    # Apply django-filter FilterSet for query params
    filterset = BulkOilOrderFilter(data, queryset=qs)
    if filterset.is_valid():
        qs = filterset.qs

    qualifying_orders: List[Order] = []

    # Evaluate exact oil bottle counts and annotate metadata
    for order in qs:
        oil_bottle_qty = 0
        bulk_oil_items = []
        all_items = []

        for item in order.order_products.all():
            if not item.product or not item.product.product:
                continue

            product_name = item.product.product.name
            qty = item.quantity or 0
            all_items.append(f"{qty}x {product_name}")

            if is_oil_bottle(product_name):
                oil_bottle_qty += qty
                bulk_oil_items.append(f"{qty}x {product_name}")

        if oil_bottle_qty >= min_oil_bottles:
            # Attach computed attributes to avoid re-computation in presentation layers
            order.annotated_oil_bottle_qty = oil_bottle_qty
            order.annotated_bulk_oil_items = ", ".join(bulk_oil_items)
            order.annotated_all_items = ", ".join(all_items)

            # Purchase date formatting
            if order.date:
                order.annotated_purchase_date = order.date.strftime("%Y-%m-%d")
            elif order.created_at:
                order.annotated_purchase_date = timezone.localtime(order.created_at).strftime("%Y-%m-%d")
            else:
                order.annotated_purchase_date = ""

            # Location formatting
            order.annotated_location_name = (
                order.location.name
                if order.location
                else (order.city or order.delivery_address or "N/A")
            )

            # Franchise label
            order.annotated_franchise_name = (
                order.franchise.name.strip()
                if (order.franchise and order.franchise.name)
                else "Direct / Unassigned"
            )

            qualifying_orders.append(order)

    return qualifying_orders, start_date, end_date
