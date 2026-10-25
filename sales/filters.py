import django_filters
from django.db.models import Q

from account.models import Franchise

from .models import InventoryChangeLog


class InventoryChangeLogExportFilter(django_filters.FilterSet):
    """
    FilterSet for exporting InventoryChangeLog entries.
    Filters:
      - start_date (YYYY-MM-DD)
      - end_date (YYYY-MM-DD)
      - franchise (Dropdown selection of Franchise)
    Restricts actions to 'add' and 'update' only.
    """

    start_date = django_filters.DateFilter(
        field_name="changed_at__date",
        lookup_expr="gte",
        label="Start Date (YYYY-MM-DD)",
    )
    end_date = django_filters.DateFilter(
        field_name="changed_at__date",
        lookup_expr="lte",
        label="End Date (YYYY-MM-DD)",
    )
    franchise = django_filters.ModelChoiceFilter(
        queryset=Franchise.objects.all(),
        field_name="inventory__franchise",
        label="Franchise",
    )
    ordering = django_filters.OrderingFilter(
        fields=(
            ("inventory__product__name", "product_name"),
            ("changed_at", "changed_at"),
        ),
        field_labels={
            "product_name": "Product Name",
            "changed_at": "Date",
        },
    )

    class Meta:
        model = InventoryChangeLog
        fields = ["start_date", "end_date", "franchise", "ordering"]


class UserInventoryLogFilter(django_filters.FilterSet):
    """
    FilterSet for UserInventoryLogs.
    Supports filtering by:
      - inventory / inventory_id: Inventory ID
      - product: Inventory ID, Product ID, or Product Name
      - product_id: Product ID
      - product_name: Product Name (icontains)
      - action: Action type (icontains)
      - changed_at: Timestamp (icontains)
      - start_date / end_date: Date range
    """

    changed_at = django_filters.CharFilter(
        field_name="changed_at", lookup_expr="icontains"
    )
    action = django_filters.CharFilter(field_name="action", lookup_expr="icontains")
    start_date = django_filters.DateFilter(
        field_name="changed_at__date",
        lookup_expr="gte",
        label="Start Date (YYYY-MM-DD)",
    )
    end_date = django_filters.DateFilter(
        field_name="changed_at__date",
        lookup_expr="lte",
        label="End Date (YYYY-MM-DD)",
    )
    inventory = django_filters.NumberFilter(
        field_name="inventory__id",
        lookup_expr="exact",
        label="Inventory ID",
    )
    inventory_id = django_filters.NumberFilter(
        field_name="inventory__id",
        lookup_expr="exact",
        label="Inventory ID",
    )
    product = django_filters.CharFilter(
        method="filter_by_product",
        label="Product (Inventory ID, Product ID, or Name)",
    )
    product_id = django_filters.NumberFilter(
        field_name="inventory__product__id",
        lookup_expr="exact",
        label="Product ID",
    )
    product_name = django_filters.CharFilter(
        field_name="inventory__product__name",
        lookup_expr="icontains",
        label="Product Name",
    )

    class Meta:
        model = InventoryChangeLog
        fields = [
            "changed_at",
            "action",
            "start_date",
            "end_date",
            "inventory",
            "inventory_id",
            "product",
            "product_id",
            "product_name",
        ]

    def filter_by_product(self, queryset, name, value):
        if not value:
            return queryset
        val_str = str(value).strip()
        if val_str.isdigit():
            val_int = int(val_str)
            return queryset.filter(
                Q(inventory__id=val_int) | Q(inventory__product__id=val_int)
            )
        return queryset.filter(inventory__product__name__icontains=val_str)

