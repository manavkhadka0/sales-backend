from datetime import timedelta

import django_filters
from django.db.models import Q
from django.utils import timezone

from tracking.constants import HEARTBEAT_TIMEOUT_MINUTES, TrackingStatus
from tracking.models import SalesPersonLocation, SalesPersonLocationHistory


class SalesPersonLocationFilter(django_filters.FilterSet):
    """
    Filter set for querying live salesperson locations.
    Supports heartbeat timeout verification and multi-state status filtering.
    """

    is_online = django_filters.BooleanFilter(method="filter_by_online")
    status = django_filters.CharFilter(method="filter_by_status")
    franchise = django_filters.NumberFilter(field_name="salesperson__franchise__id")
    distributor = django_filters.NumberFilter(field_name="salesperson__distributor__id")
    search = django_filters.CharFilter(method="filter_by_search")

    class Meta:
        model = SalesPersonLocation
        fields = ["is_online", "status", "franchise", "distributor", "search"]

    def filter_by_online(self, queryset, name, value):
        threshold = timezone.now() - timedelta(minutes=HEARTBEAT_TIMEOUT_MINUTES)
        if value is True:
            return queryset.filter(is_online=True, last_updated_at__gte=threshold)
        elif value is False:
            return queryset.filter(Q(is_online=False) | Q(last_updated_at__lt=threshold))
        return queryset

    def filter_by_status(self, queryset, name, value):
        if not value:
            return queryset
        val = str(value).upper()
        threshold = timezone.now() - timedelta(minutes=HEARTBEAT_TIMEOUT_MINUTES)
        if val == TrackingStatus.ONLINE:
            return queryset.filter(is_online=True, last_updated_at__gte=threshold)
        elif val == TrackingStatus.INACTIVE:
            return queryset.filter(is_online=True, last_updated_at__lt=threshold)
        elif val == TrackingStatus.OFFLINE:
            return queryset.filter(is_online=False)
        return queryset

    def filter_by_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(salesperson__username__icontains=value)
            | Q(salesperson__first_name__icontains=value)
            | Q(salesperson__last_name__icontains=value)
            | Q(salesperson__phone_number__icontains=value)
        )


class SalesPersonLocationHistoryFilter(django_filters.FilterSet):
    """
    Filter set for querying salesperson route history breadcrumbs.
    """

    salesperson = django_filters.NumberFilter(field_name="salesperson_id")
    date = django_filters.DateFilter(field_name="created_at__date")
    start_datetime = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    end_datetime = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )

    class Meta:
        model = SalesPersonLocationHistory
        fields = ["salesperson", "date", "start_datetime", "end_datetime"]
