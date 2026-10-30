from datetime import timedelta

import django_filters
from django.utils import timezone

from offlineSales.models import (
    Attendance,
    OfflineCustomer,
    OfflineOrder,
    OfflinePaymentHistory,
    OfflineSalesAccess,
)


class OfflineCustomerFilter(django_filters.FilterSet):
    store_name = django_filters.CharFilter(lookup_expr="icontains")
    contact_person = django_filters.CharFilter(lookup_expr="icontains")
    phone_number = django_filters.CharFilter(lookup_expr="icontains")
    address = django_filters.CharFilter(lookup_expr="icontains")
    franchise = django_filters.NumberFilter(field_name="franchise_id")
    sales_person = django_filters.NumberFilter(field_name="sales_person_id")
    is_active = django_filters.BooleanFilter()
    start_date = django_filters.DateFilter(
        field_name="created_at__date", lookup_expr="gte"
    )
    end_date = django_filters.DateFilter(
        field_name="created_at__date", lookup_expr="lte"
    )
    has_pending_credit = django_filters.BooleanFilter(
        method="filter_has_pending_credit"
    )

    class Meta:
        model = OfflineCustomer
        fields = [
            "store_name",
            "contact_person",
            "phone_number",
            "address",
            "franchise",
            "sales_person",
            "is_active",
            "start_date",
            "end_date",
            "has_pending_credit",
        ]

    def filter_has_pending_credit(self, queryset, name, value):
        if value is True:
            # Check for customers with unpaid or partial remaining amount
            return queryset.filter(annotated_total_remaining__gt=0)
        elif value is False:
            return queryset.filter(annotated_total_remaining=0)
        return queryset


class OfflineOrderFilter(django_filters.FilterSet):
    order_code = django_filters.CharFilter(lookup_expr="icontains")
    customer = django_filters.NumberFilter(field_name="customer_id")
    customer_store_name = django_filters.CharFilter(
        field_name="customer__store_name", lookup_expr="icontains"
    )
    customer_phone = django_filters.CharFilter(
        field_name="customer__phone_number", lookup_expr="icontains"
    )
    franchise = django_filters.NumberFilter(field_name="franchise_id")
    sales_person = django_filters.NumberFilter(field_name="sales_person_id")
    order_status = django_filters.ChoiceFilter(choices=OfflineOrder.OrderStatus.choices)
    payment_status = django_filters.ChoiceFilter(
        choices=OfflineOrder.PaymentStatus.choices
    )
    order_date = django_filters.DateFilter(field_name="order_date")
    start_date = django_filters.DateFilter(field_name="order_date", lookup_expr="gte")
    end_date = django_filters.DateFilter(field_name="order_date", lookup_expr="lte")

    class Meta:
        model = OfflineOrder
        fields = [
            "order_code",
            "customer",
            "customer_store_name",
            "customer_phone",
            "franchise",
            "sales_person",
            "order_status",
            "payment_status",
            "order_date",
            "start_date",
            "end_date",
        ]


class OfflinePaymentHistoryFilter(django_filters.FilterSet):
    order = django_filters.NumberFilter(field_name="order_id")
    order_code = django_filters.CharFilter(
        field_name="order__order_code", lookup_expr="icontains"
    )
    customer = django_filters.NumberFilter(field_name="order__customer_id")
    payment_method = django_filters.ChoiceFilter(
        choices=OfflinePaymentHistory.PaymentMethod.choices
    )
    recorded_by = django_filters.NumberFilter(field_name="recorded_by_id")
    start_date = django_filters.DateFilter(
        field_name="payment_date__date", lookup_expr="gte"
    )
    end_date = django_filters.DateFilter(
        field_name="payment_date__date", lookup_expr="lte"
    )

    class Meta:
        model = OfflinePaymentHistory
        fields = [
            "order",
            "order_code",
            "customer",
            "payment_method",
            "recorded_by",
            "start_date",
            "end_date",
        ]


class OfflineOrderCreditReminderFilter(django_filters.FilterSet):
    customer = django_filters.NumberFilter(field_name="customer_id")
    customer_store_name = django_filters.CharFilter(
        field_name="customer__store_name", lookup_expr="icontains"
    )
    customer_phone = django_filters.CharFilter(
        field_name="customer__phone_number", lookup_expr="icontains"
    )
    franchise = django_filters.NumberFilter(field_name="franchise_id")
    sales_person = django_filters.NumberFilter(field_name="sales_person_id")
    is_overdue = django_filters.BooleanFilter(method="filter_is_overdue")
    days_threshold = django_filters.NumberFilter(method="filter_days_threshold")

    class Meta:
        model = OfflineOrder
        fields = [
            "customer",
            "customer_store_name",
            "customer_phone",
            "franchise",
            "sales_person",
            "is_overdue",
            "days_threshold",
        ]

    def filter_is_overdue(self, queryset, name, value):
        ninety_days_ago = timezone.localdate() - timedelta(days=90)
        if value is True:
            return queryset.filter(order_date__lte=ninety_days_ago)
        elif value is False:
            return queryset.filter(order_date__gt=ninety_days_ago)
        return queryset

    def filter_days_threshold(self, queryset, name, value):
        if value is not None:
            cutoff = timezone.localdate() - timedelta(days=int(value))
            return queryset.filter(order_date__lte=cutoff)
        return queryset


class OfflineSalesAccessFilter(django_filters.FilterSet):
    user = django_filters.NumberFilter(field_name="user_id")
    role = django_filters.CharFilter(field_name="user__role", lookup_expr="iexact")
    start_date = django_filters.DateFilter(
        field_name="granted_at__date", lookup_expr="gte"
    )
    end_date = django_filters.DateFilter(
        field_name="granted_at__date", lookup_expr="lte"
    )

    class Meta:
        model = OfflineSalesAccess
        fields = ["user", "role", "start_date", "end_date"]


class AttendanceFilter(django_filters.FilterSet):
    sales_person = django_filters.NumberFilter(field_name="sales_person_id")
    start_date = django_filters.DateFilter(
        field_name="attendance_date", lookup_expr="gte"
    )
    end_date = django_filters.DateFilter(
        field_name="attendance_date", lookup_expr="lte"
    )

    class Meta:
        model = Attendance
        fields = ["sales_person", "start_date", "end_date"]
