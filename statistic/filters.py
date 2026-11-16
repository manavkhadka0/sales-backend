from datetime import datetime, time, timedelta

from django.db.models import Q
from django.utils import timezone
from django_filters import rest_framework as django_filters

from sales.models import Order

from .models import Report


class ReportFilter(django_filters.FilterSet):
    franchise = django_filters.CharFilter(
        field_name="franchise__id", lookup_expr="exact"
    )
    start_date = django_filters.DateFilter(method="filter_start_date")
    end_date = django_filters.DateFilter(method="filter_end_date")
    date = django_filters.DateFilter(field_name="date", lookup_expr="exact")

    class Meta:
        model = Report
        fields = ["franchise", "start_date", "end_date", "date"]

    def filter_start_date(self, queryset, name, value):
        if not value:
            return queryset
        start_date = timezone.make_aware(datetime.combine(value, datetime.min.time()))
        return queryset.filter(date__gte=start_date)

    def filter_end_date(self, queryset, name, value):
        if not value:
            return queryset
        end_date = timezone.make_aware(datetime.combine(value, datetime.max.time()))
        return queryset.filter(date__lte=end_date)


class FranchiseSalesReportFilter(django_filters.FilterSet):
    """
    Filter for Franchise Sales & Product Breakdown Report.
    Supports filtering by:
    - franchise: Franchise ID or name/short_form
    - distributor: Distributor ID
    - date: Single date (YYYY-MM-DD)
    - start_date: Range start (YYYY-MM-DD)
    - end_date: Range end (YYYY-MM-DD)
    - filter: Preset options (today [12am-12pm], yesterday, this_week, this_month, last_month, weekly, monthly, all)
    - include_cancelled: Optional boolean to include cancelled/returned orders
    - breakdown_by: 'category' (default) or 'product'
    """

    franchise = django_filters.CharFilter(method="filter_franchise")
    distributor = django_filters.CharFilter(method="filter_distributor")
    date = django_filters.DateFilter(method="filter_date")
    start_date = django_filters.DateFilter(method="filter_start_date")
    end_date = django_filters.DateFilter(method="filter_end_date")
    filter = django_filters.CharFilter(method="filter_preset")
    include_cancelled = django_filters.BooleanFilter(method="filter_noop")
    breakdown_by = django_filters.CharFilter(method="filter_noop")

    class Meta:
        model = Order
        fields = [
            "franchise",
            "distributor",
            "date",
            "start_date",
            "end_date",
            "filter",
            "include_cancelled",
            "breakdown_by",
        ]

    def filter_noop(self, queryset, name, value):
        return queryset

    def filter_franchise(self, queryset, name, value):
        if not value:
            return queryset
        val_str = str(value).strip()
        if val_str.isdigit():
            return queryset.filter(franchise_id=int(val_str))
        return queryset.filter(
            Q(franchise__short_form__iexact=val_str)
            | Q(franchise__name__icontains=val_str)
        )

    def filter_distributor(self, queryset, name, value):
        if not value:
            return queryset
        if str(value).isdigit():
            return queryset.filter(distributor_id=int(value))
        return queryset

    def filter_date(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(Q(date=value) | Q(created_at__date=value))

    def filter_start_date(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(Q(date__gte=value) | Q(created_at__date__gte=value))

    def filter_end_date(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(Q(date__lte=value) | Q(created_at__date__lte=value))

    def filter_preset(self, queryset, name, value):
        if not value:
            return queryset
        now_local = timezone.localtime(timezone.now())
        today = now_local.date()
        tz = timezone.get_current_timezone()
        val = str(value).lower().strip()
        if val == "today":
            start_dt = timezone.make_aware(datetime.combine(today, time(0, 0, 0)), tz)
            end_dt = timezone.make_aware(datetime.combine(today, time(12, 0, 0)), tz)
            return queryset.filter(created_at__gte=start_dt, created_at__lte=end_dt)
        elif val == "yesterday":
            yesterday = today - timedelta(days=1)
            return queryset.filter(Q(date=yesterday) | Q(created_at__date=yesterday))
        elif val in ["this_week", "weekly"]:
            start_week = today - timedelta(days=today.weekday())
            return queryset.filter(
                Q(date__gte=start_week, date__lte=today)
                | Q(created_at__date__gte=start_week, created_at__date__lte=today)
            )
        elif val in ["this_month", "monthly"]:
            start_month = today.replace(day=1)
            return queryset.filter(
                Q(date__gte=start_month, date__lte=today)
                | Q(created_at__date__gte=start_month, created_at__date__lte=today)
            )
        elif val == "last_month":
            first_this_month = today.replace(day=1)
            last_day_last_month = first_this_month - timedelta(days=1)
            first_day_last_month = last_day_last_month.replace(day=1)
            return queryset.filter(
                Q(date__gte=first_day_last_month, date__lte=last_day_last_month)
                | Q(
                    created_at__date__gte=first_day_last_month,
                    created_at__date__lte=last_day_last_month,
                )
            )
        return queryset
