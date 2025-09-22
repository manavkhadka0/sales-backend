from django.db import transaction
from rest_framework import generics

from .models import FestConfig, SalesGroup
from .serializers import (
    FestConfigSerializer,
    SalesGroupSerializer,
    SalesGroupSerializer2,
)


class SalesGroupListCreateView(generics.ListCreateAPIView):
    queryset = SalesGroup.objects.all().order_by("-created_at")
    serializer_class = SalesGroupSerializer

    def get_serializer_class(self):
        if self.request.method == "GET":
            return SalesGroupSerializer2
        return SalesGroupSerializer

    def perform_create(self, serializer):
        group = serializer.save()
        # Attach the new group to the singleton FestConfig
        config = FestConfig.get_solo()
        config.sales_group.add(group)
        if config.has_sales_fest is False:
            config.has_sales_fest = True
        config.save()


class SalesGroupDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = SalesGroup.objects.all()
    serializer_class = SalesGroupSerializer


class FestConfigRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    serializer_class = FestConfigSerializer

    def get_object(self):
        return FestConfig.get_solo()

    def perform_update(self, serializer):
        user = self.request.user
        # Default to existing franchise if not a Franchise user or missing attribute
        franchise = getattr(serializer.instance, "franchise", None)
        if getattr(user, "role", None) == "Franchise":
            franchise = getattr(user, "franchise", franchise)

        with transaction.atomic():
            instance = serializer.save(franchise=franchise)
            # If has_sales_fest is explicitly set to False in this update, delete all SalesGroup
            if serializer.validated_data.get("has_sales_fest") is False:
                SalesGroup.objects.all().delete()
                # Also clear M2M in case of constraints/order
                instance.sales_group.clear()
