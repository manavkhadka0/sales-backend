import django_filters
from django.db.models import Q

from .models import DarazLocation


class DarazLocationFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search")

    class Meta:
        model = DarazLocation
        fields = ["search"]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset

        # Filter where city contains search term OR area contains search term
        return queryset.filter(Q(city__icontains=value) | Q(area__icontains=value))
