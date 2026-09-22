import django_filters
from django.db import models

from .models import (
    CustomerTreatment,
    Image,
    PackageChoice,
    PaymentHistory,
    PaymentMethod,
    TreatmentType,
)


class CustomerTreatmentFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search", label="Search")
    treatment_type = django_filters.ChoiceFilter(choices=TreatmentType.choices)
    package = django_filters.ChoiceFilter(choices=PackageChoice.choices)
    payment_method = django_filters.ChoiceFilter(choices=PaymentMethod.choices)
    franchise = django_filters.NumberFilter(field_name="franchise__id")
    service_by = django_filters.NumberFilter(field_name="service_by__id")
    start_date = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    end_date = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = CustomerTreatment
        fields = [
            "treatment_type",
            "package",
            "payment_method",
            "franchise",
            "service_by",
        ]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            models.Q(name__icontains=value) | models.Q(phone_number__icontains=value)
        )


class ImageFilter(django_filters.FilterSet):
    customer_treatment = django_filters.NumberFilter(
        field_name="customer_treatment__id"
    )
    day_number = django_filters.NumberFilter(field_name="day_number")

    class Meta:
        model = Image
        fields = ["customer_treatment", "day_number"]


class PaymentHistoryFilter(django_filters.FilterSet):
    customer_treatment = django_filters.NumberFilter(
        field_name="customer_treatment__id"
    )
    payment_method = django_filters.ChoiceFilter(choices=PaymentMethod.choices)
    payment_date_gte = django_filters.DateTimeFilter(
        field_name="payment_date", lookup_expr="gte"
    )
    payment_date_lte = django_filters.DateTimeFilter(
        field_name="payment_date", lookup_expr="lte"
    )

    class Meta:
        model = PaymentHistory
        fields = ["customer_treatment", "payment_method"]
