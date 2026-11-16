from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Optional

from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from account.models import Franchise
from sales.constants import EXCLUDED_STATUSES
from sales.models import Order, OrderProduct

# Official finished products
FINISHED_PRODUCTS = [
    "Shampoo Sachet",
    "Shampoo Bottle",
    "Hair Oil Sachet",
    "Baldness Oil Bottle",
    "Hairfall Oil Bottle",
    "Dandruff Oil Bottle",
    "Brightening Cream",
    "Face Wash",
    "Body Lotion",
    "Yachu Hair Oil",
]

# Canonical category mapping (matching report specifications)
PRODUCT_TO_CATEGORY_MAP = {
    "Shampoo Sachet": "Sachet shampoo",
    "Shampoo Bottle": "B. Shampoo",
    "Hair Oil Sachet": "Sachet oil",
    "Baldness Oil Bottle": "Hair Oil",
    "Hairfall Oil Bottle": "Hair Oil",
    "Dandruff Oil Bottle": "Hair Oil",
    "Yachu Hair Oil": "Hair Oil",
    "Brightening Cream": "Brightening Cream",
    "Face Wash": "Face Wash",
    "Body Lotion": "Body Lotion",
}


def match_finished_product(product_name: str) -> Optional[str]:
    """
    Matches a product name against the 10 official finished products:
    1. Shampoo Sachet
    2. Shampoo Bottle
    3. Hair Oil Sachet
    4. Baldness Oil Bottle
    5. Hairfall Oil Bottle
    6. Dandruff Oil Bottle
    7. Brightening Cream
    8. Face Wash
    9. Body Lotion
    10. Yachu Hair Oil

    Returns canonical product name if it matches, else None (ignoring non-finished products).
    """
    if not product_name:
        return None

    nl = product_name.lower().strip()

    # Ignore raw materials, factory ingredients, stickers, and packaging sets
    if any(
        k in nl for k in ["sticker", "extract", "coconot", "set", "raw", "ingredient"]
    ):
        return None

    # Sachets
    if "sachet" in nl:
        if "shampoo" in nl:
            return "Shampoo Sachet"
        if "oil" in nl:
            return "Hair Oil Sachet"
        return None

    # Shampoo Bottle
    if "shampoo" in nl and "sachet" not in nl:
        return "Shampoo Bottle"

    # Face Wash
    if "facewash" in nl or "face wash" in nl:
        return "Face Wash"

    # Body Lotion
    if "body lotion" in nl or "lotion" in nl:
        return "Body Lotion"

    # Brightening Cream
    if any(k in nl for k in ["brightening", "brightning", "cream"]):
        return "Brightening Cream"

    # Specific Hair Oil Bottles
    if "baldness" in nl:
        return "Baldness Oil Bottle"
    if "hairfall" in nl:
        return "Hairfall Oil Bottle"
    if "dandruff" in nl:
        return "Dandruff Oil Bottle"
    if "yachu hair oil" in nl or "yachu oil" in nl:
        return "Yachu Hair Oil"
    if ("hair oil" in nl or "hairoil" in nl) and "sachet" not in nl:
        return "Yachu Hair Oil"

    return None


def apply_date_and_status_filters(
    queryset,
    filter_params: Dict[str, Any],
):
    """
    Apply date and preset filters to the Order queryset.
    Excludes cancelled and returned order statuses.

    Default behavior (when no date or preset filter is provided, or filter=today):
    Filters for today's orders between 12:00 AM (00:00:00) and 12:00 PM (12:00:00) in local timezone.
    """
    include_cancelled = filter_params.get("include_cancelled")
    if not (include_cancelled and str(include_cancelled).lower() in ["true", "1"]):
        queryset = queryset.exclude(order_status__in=EXCLUDED_STATUSES)

    date_str = filter_params.get("date")
    start_date_str = filter_params.get("start_date")
    end_date_str = filter_params.get("end_date")
    preset_filter = filter_params.get("filter")

    now_local = timezone.localtime(timezone.now())
    today = now_local.date()
    tz = timezone.get_current_timezone()

    if date_str:
        try:
            target_date = datetime.strptime(str(date_str).strip(), "%Y-%m-%d").date()
            queryset = queryset.filter(
                Q(date=target_date) | Q(created_at__date=target_date)
            )
        except ValueError:
            pass

    elif start_date_str or end_date_str:
        if start_date_str:
            try:
                start_date = datetime.strptime(
                    str(start_date_str).strip(), "%Y-%m-%d"
                ).date()
                queryset = queryset.filter(
                    Q(date__gte=start_date) | Q(created_at__date__gte=start_date)
                )
            except ValueError:
                pass
        if end_date_str:
            try:
                end_date = datetime.strptime(
                    str(end_date_str).strip(), "%Y-%m-%d"
                ).date()
                queryset = queryset.filter(
                    Q(date__lte=end_date) | Q(created_at__date__lte=end_date)
                )
            except ValueError:
                pass

    elif preset_filter:
        val = str(preset_filter).lower().strip()
        if val == "today":
            start_dt = timezone.make_aware(datetime.combine(today, time(0, 0, 0)), tz)
            end_dt = timezone.make_aware(datetime.combine(today, time(12, 0, 0)), tz)
            queryset = queryset.filter(created_at__gte=start_dt, created_at__lte=end_dt)
        elif val == "yesterday":
            yesterday = today - timedelta(days=1)
            queryset = queryset.filter(
                Q(date=yesterday) | Q(created_at__date=yesterday)
            )
        elif val in ["this_week", "weekly"]:
            start_week = today - timedelta(days=today.weekday())
            queryset = queryset.filter(
                Q(date__gte=start_week, date__lte=today)
                | Q(created_at__date__gte=start_week, created_at__date__lte=today)
            )
        elif val in ["this_month", "monthly"]:
            start_month = today.replace(day=1)
            queryset = queryset.filter(
                Q(date__gte=start_month, date__lte=today)
                | Q(created_at__date__gte=start_month, created_at__date__lte=today)
            )
        elif val == "last_month":
            first_this_month = today.replace(day=1)
            last_day_last_month = first_this_month - timedelta(days=1)
            first_day_last_month = last_day_last_month.replace(day=1)
            queryset = queryset.filter(
                Q(date__gte=first_day_last_month, date__lte=last_day_last_month)
                | Q(
                    created_at__date__gte=first_day_last_month,
                    created_at__date__lte=last_day_last_month,
                )
            )
        elif val in ["all", "all_time"]:
            pass
    else:
        # DEFAULT: Today's report from 12:00 AM (00:00:00) to 12:00 PM (12:00:00) in local timezone
        start_dt = timezone.make_aware(datetime.combine(today, time(0, 0, 0)), tz)
        end_dt = timezone.make_aware(datetime.combine(today, time(12, 0, 0)), tz)
        queryset = queryset.filter(created_at__gte=start_dt, created_at__lte=end_dt)

    return queryset


def get_franchise_sales_report(
    user,
    filter_params: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Selector to generate the franchise sales and product breakdown report.
    Access restricted to SuperAdmin users only.
    Returns a list of franchise report objects (including 'Main Page' franchise).
    Each item contains:
    - franchise_id (optional int)
    - franchise_name (str, e.g. 'Main Page', '(NU)', 'sankhamul')
    - total_sales (int)
    - online_sales (int)
    - office_sale (int)
    - product_breakdown (dict of product name to quantity > 0)
    """
    if not (
        user
        and user.is_authenticated
        and (user.is_superuser or getattr(user, "role", None) == "SuperAdmin")
    ):
        raise PermissionDenied("Only SuperAdmin users can view this report.")

    if filter_params is None:
        filter_params = {}

    franchise_param = filter_params.get("franchise")
    distributor_param = filter_params.get("distributor")
    breakdown_by = filter_params.get("breakdown_by", "category").lower().strip()

    is_single_franchise_filter = False

    # Filter franchises belonging to user.factory (e.g. Yachu)
    if getattr(user, "factory", None):
        franchises_qs = Franchise.objects.filter(
            distributor__factory=user.factory
        ).order_by("name")
    else:
        franchises_qs = Franchise.objects.all().order_by("name")

    if franchise_param:
        is_single_franchise_filter = True
        if str(franchise_param).isdigit():
            franchises_qs = franchises_qs.filter(id=int(franchise_param))
        else:
            franchises_qs = franchises_qs.filter(
                Q(short_form__iexact=str(franchise_param).strip())
                | Q(name__icontains=str(franchise_param).strip())
            )
    elif distributor_param and str(distributor_param).isdigit():
        franchises_qs = franchises_qs.filter(distributor_id=int(distributor_param))

    franchises = list(franchises_qs.only("id", "name", "short_form"))
    franchise_ids = [f.id for f in franchises]

    # Base orders: scoped to user.factory if set, plus date/status filters
    if getattr(user, "factory", None):
        base_orders = Order.objects.filter(
            Q(factory=user.factory) | Q(franchise__distributor__factory=user.factory)
        )
    else:
        base_orders = Order.objects.all()

    base_orders = apply_date_and_status_filters(base_orders, filter_params)

    # 1 query: Aggregate order counts per franchise (Online vs Office Visit)
    order_stats_qs = (
        base_orders
        .filter(franchise_id__in=franchise_ids)
        .values("franchise_id")
        .annotate(
            total_orders=Count("id"),
            office_orders=Count("id", filter=Q(payment_method="Office Visit")),
            online_orders=Count("id", filter=~Q(payment_method="Office Visit")),
        )
    )
    order_stats_map = {row["franchise_id"]: row for row in order_stats_qs}

    # 1 query: Aggregate product quantities per franchise and payment method
    product_stats_qs = (
        OrderProduct.objects
        .filter(order__in=base_orders.filter(franchise_id__in=franchise_ids))
        .values(
            "order__franchise_id",
            "product__product__id",
            "product__product__name",
            "order__payment_method",
        )
        .annotate(total_quantity=Sum("quantity"))
    )

    franchise_product_rows: Dict[int, List[Dict[str, Any]]] = {}
    for row in product_stats_qs:
        fid = row["order__franchise_id"]
        franchise_product_rows.setdefault(fid, []).append(row)

    franchise_reports = []
    main_page_entry_index = None

    for f in franchises:
        fid = f.id
        f_stats = order_stats_map.get(
            fid, {"total_orders": 0, "office_orders": 0, "online_orders": 0}
        )
        online_count = f_stats["online_orders"]
        office_count = f_stats["office_orders"]
        total_sales = f_stats["total_orders"]

        # Omit franchise if 0 sales (unless single franchise is explicitly requested)
        if total_sales == 0 and not is_single_franchise_filter:
            continue

        f_product_totals: Dict[str, int] = {}
        p_rows = franchise_product_rows.get(fid, [])
        for row in p_rows:
            p_name = row["product__product__name"] or ""
            qty = row["total_quantity"] or 0
            if qty <= 0:
                continue

            matched = match_finished_product(p_name)
            if not matched:
                # Exclude non-finished products
                continue

            label = (
                matched
                if breakdown_by == "product"
                else PRODUCT_TO_CATEGORY_MAP[matched]
            )
            f_product_totals[label] = f_product_totals.get(label, 0) + qty

        # Only include products where quantity > 0
        f_product_breakdown = {
            name: qty for name, qty in f_product_totals.items() if qty > 0
        }

        # Franchise naming: "(NU)" if short_form exists, else franchise name
        franchise_name_formatted = f"({f.short_form})" if f.short_form else f.name

        entry = {
            "franchise_id": f.id,
            "franchise_name": franchise_name_formatted,
            "total_sales": total_sales,
            "online_sales": online_count,
            "office_sale": office_count,
            "product_breakdown": f_product_breakdown,
        }

        if "main page" in f.name.lower() or (
            f.short_form and "main" in f.short_form.lower()
        ):
            main_page_entry_index = len(franchise_reports)

        franchise_reports.append(entry)

    # Check unassigned orders (orders with franchise=None) representing Main Page if not already covered
    unassigned_orders = base_orders.filter(franchise__isnull=True)
    if unassigned_orders.exists() and not is_single_franchise_filter:
        unassigned_stats = unassigned_orders.aggregate(
            total_orders=Count("id"),
            office_orders=Count("id", filter=Q(payment_method="Office Visit")),
            online_orders=Count("id", filter=~Q(payment_method="Office Visit")),
        )
        unassigned_product_stats = (
            OrderProduct.objects
            .filter(order__in=unassigned_orders)
            .values("product__product__name")
            .annotate(total_quantity=Sum("quantity"))
        )
        unassigned_breakdown: Dict[str, int] = {}
        for row in unassigned_product_stats:
            p_name = row["product__product__name"] or ""
            qty = row["total_quantity"] or 0
            if qty <= 0:
                continue

            matched = match_finished_product(p_name)
            if not matched:
                continue

            label = (
                matched
                if breakdown_by == "product"
                else PRODUCT_TO_CATEGORY_MAP[matched]
            )
            unassigned_breakdown[label] = unassigned_breakdown.get(label, 0) + qty

        unassigned_total = unassigned_stats["total_orders"] or 0
        if unassigned_total > 0:
            if main_page_entry_index is not None:
                # Merge into existing Main Page franchise
                existing = franchise_reports[main_page_entry_index]
                existing["total_sales"] += unassigned_total
                existing["online_sales"] += unassigned_stats["online_orders"] or 0
                existing["office_sale"] += unassigned_stats["office_orders"] or 0
                for name, qty in unassigned_breakdown.items():
                    existing["product_breakdown"][name] = (
                        existing["product_breakdown"].get(name, 0) + qty
                    )
            else:
                franchise_reports.append({
                    "franchise_id": None,
                    "franchise_name": "Main Page",
                    "total_sales": unassigned_total,
                    "online_sales": unassigned_stats["online_orders"] or 0,
                    "office_sale": unassigned_stats["office_orders"] or 0,
                    "product_breakdown": unassigned_breakdown,
                })

    # Sort so 'Main Page' appears first if present, followed alphabetically by franchise_name
    franchise_reports.sort(
        key=lambda x: (
            0 if "main page" in x["franchise_name"].lower() else 1,
            x["franchise_name"].lower(),
        )
    )

    return franchise_reports
