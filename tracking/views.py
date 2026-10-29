from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status
from rest_framework.exceptions import NotFound
from rest_framework.generics import CreateAPIView, ListAPIView, RetrieveAPIView
from rest_framework.response import Response

from tracking.filters import (
    SalesPersonLocationFilter,
    SalesPersonLocationHistoryFilter,
)
from tracking.models import SalesPersonLocationHistory
from tracking.permissions import (
    CanViewSalesPersonTracking,
    IsOfflineSalesPerson,
    IsSalesPersonOrSupervisor,
)
from tracking.selectors.location_selector import (
    get_salesperson_location_by_id,
    get_salesperson_location_history_qs,
    get_salesperson_locations_qs,
)
from tracking.serializers import (
    SalesPersonBatchPingSerializer,
    SalesPersonLiveLocationSerializer,
    SalesPersonLocationHistorySerializer,
    SalesPersonLocationPingSerializer,
    SalesPersonToggleOnlineSerializer,
)
from tracking.services.location_service import (
    bulk_record_offline_pings,
    toggle_salesperson_online_status,
    update_salesperson_location,
)


class SalesPersonLocationPingAPIView(CreateAPIView):
    """
    HTTP REST endpoint for mobile apps to submit live GPS location pings.
    """

    permission_classes = [permissions.IsAuthenticated, IsOfflineSalesPerson]
    serializer_class = SalesPersonLocationPingSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        location, created = update_salesperson_location(
            salesperson=request.user,
            latitude=data["latitude"],
            longitude=data["longitude"],
            accuracy=data.get("accuracy"),
            recorded_at=data.get("recorded_at"),
        )

        response_serializer = SalesPersonLiveLocationSerializer(location)
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(response_serializer.data, status=status_code)


class SalesPersonBatchLocationPingAPIView(CreateAPIView):
    """
    HTTP REST endpoint for uploading buffered GPS points stored while offline in the field.
    """

    permission_classes = [permissions.IsAuthenticated, IsOfflineSalesPerson]
    serializer_class = SalesPersonBatchPingSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        pings = serializer.validated_data["pings"]
        count = bulk_record_offline_pings(salesperson=request.user, pings=pings)

        return Response(
            {
                "status": "success",
                "message": f"Successfully synced {count} offline location pings.",
                "synced_count": count,
            },
            status=status.HTTP_201_CREATED,
        )


class SalesPersonToggleOnlineAPIView(CreateAPIView):
    """
    HTTP REST endpoint for salespersons to start or end field shifts.
    """

    permission_classes = [permissions.IsAuthenticated, IsOfflineSalesPerson]
    serializer_class = SalesPersonToggleOnlineSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        location = toggle_salesperson_online_status(
            salesperson=request.user,
            is_online=serializer.validated_data["is_online"],
        )

        response_serializer = SalesPersonLiveLocationSerializer(location)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class SalesPersonSelfLocationAPIView(RetrieveAPIView):
    """
    HTTP REST endpoint for salespersons to view their own latest tracking status.
    """

    permission_classes = [permissions.IsAuthenticated, IsOfflineSalesPerson]
    serializer_class = SalesPersonLiveLocationSerializer

    def get_object(self):
        location = get_salesperson_location_by_id(
            salesperson_id=self.request.user.id,
            user=self.request.user,
        )
        if not location:
            raise NotFound(detail="No location recorded yet for your account.")
        return location


class SalesPersonLocationListAPIView(ListAPIView):
    """
    HTTP REST endpoint for managers and supervisors to view live locations of field salespersons.
    Data is scoped strictly to the supervisor's franchise or distributor.
    """

    permission_classes = [permissions.IsAuthenticated, CanViewSalesPersonTracking]
    serializer_class = SalesPersonLiveLocationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = SalesPersonLocationFilter

    def get_queryset(self):
        return get_salesperson_locations_qs(user=self.request.user)


class SalesPersonLocationDetailAPIView(RetrieveAPIView):
    """
    HTTP REST endpoint to view the live location of a specific salesperson.
    """

    permission_classes = [permissions.IsAuthenticated, CanViewSalesPersonTracking]
    serializer_class = SalesPersonLiveLocationSerializer

    def get_queryset(self):
        return get_salesperson_locations_qs(user=self.request.user)


class SalesPersonLocationHistoryListAPIView(ListAPIView):
    """
    HTTP REST endpoint to query route playback breadcrumbs for a salesperson.
    """

    permission_classes = [permissions.IsAuthenticated, IsSalesPersonOrSupervisor]
    serializer_class = SalesPersonLocationHistorySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = SalesPersonLocationHistoryFilter

    def get_queryset(self):
        salesperson_id = self.kwargs.get(
            "salesperson_id"
        ) or self.request.query_params.get("salesperson")
        if not salesperson_id:
            # If the requester is an offline salesperson, default to self
            if getattr(self.request.user, "role", None) in [
                "Offline_SalesPerson",
                "SalesPerson",
            ]:
                salesperson_id = self.request.user.id
            else:
                return SalesPersonLocationHistory.objects.none()

        return get_salesperson_location_history_qs(
            salesperson_id=int(salesperson_id),
            user=self.request.user,
        )
