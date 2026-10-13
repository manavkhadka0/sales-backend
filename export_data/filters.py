import django_filters

from sales.models import Order


class OrderCSVExportFilter(django_filters.FilterSet):
    """
    FilterSet for exporting orders.
    Supports date ranges, order dates, franchise, status, logistics, and location.
    """

    order_ids = django_filters.BaseInFilter(
        field_name="id",
        lookup_expr="in",
        help_text="Comma-separated list of order IDs (e.g. 1,2,3)",
    )
    start_date = django_filters.DateFilter(
        field_name="created_at__date",
        lookup_expr="gte",
        help_text="Filter orders created on or after this date (YYYY-MM-DD)",
    )
    end_date = django_filters.DateFilter(
        field_name="created_at__date",
        lookup_expr="lte",
        help_text="Filter orders created on or before this date (YYYY-MM-DD)",
    )
    date_from = django_filters.DateFilter(
        field_name="created_at__date",
        lookup_expr="gte",
        help_text="Alias for start_date (YYYY-MM-DD)",
    )
    date_to = django_filters.DateFilter(
        field_name="created_at__date",
        lookup_expr="lte",
        help_text="Alias for end_date (YYYY-MM-DD)",
    )
    order_date_from = django_filters.DateFilter(
        field_name="date",
        lookup_expr="gte",
        help_text="Filter by order date from (YYYY-MM-DD)",
    )
    order_date_to = django_filters.DateFilter(
        field_name="date",
        lookup_expr="lte",
        help_text="Filter by order date up to (YYYY-MM-DD)",
    )
    franchise = django_filters.CharFilter(
        method="filter_franchise",
        help_text="Filter by franchise ID or franchise name",
    )
    franchise_id = django_filters.NumberFilter(
        field_name="franchise_id",
        help_text="Filter by franchise ID",
    )
    order_status = django_filters.CharFilter(
        field_name="order_status",
        lookup_expr="iexact",
        help_text="Filter orders by status",
    )
    logistics = django_filters.CharFilter(
        field_name="logistics",
        lookup_expr="iexact",
        help_text="Filter orders by logistics provider",
    )
    location = django_filters.NumberFilter(
        field_name="location_id",
        help_text="Filter by location ID",
    )
    salesperson = django_filters.CharFilter(
        field_name="sales_person__phone_number",
        lookup_expr="icontains",
        help_text="Filter orders by salesperson phone number",
    )

    class Meta:
        model = Order
        fields = [
            "franchise",
            "order_status",
            "logistics",
            "location",
        ]

    def filter_franchise(self, queryset, name, value):
        if not value:
            return queryset
        val_str = str(value).strip()
        if val_str.isdigit():
            return queryset.filter(franchise_id=int(val_str))
        return queryset.filter(franchise__name__icontains=val_str)
