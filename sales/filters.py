import django_filters

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
