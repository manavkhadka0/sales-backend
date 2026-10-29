from django.urls import path

from tracking.views import (
    SalesPersonBatchLocationPingAPIView,
    SalesPersonLocationDetailAPIView,
    SalesPersonLocationHistoryListAPIView,
    SalesPersonLocationListAPIView,
    SalesPersonLocationPingAPIView,
    SalesPersonSelfLocationAPIView,
    SalesPersonToggleOnlineAPIView,
)

app_name = "tracking"

urlpatterns = [
    # Salesperson device endpoints (Offline_SalesPerson)
    path(
        "location/",
        SalesPersonLocationPingAPIView.as_view(),
        name="salesperson-location-ping",
    ),
    path(
        "locations/batch/",
        SalesPersonBatchLocationPingAPIView.as_view(),
        name="salesperson-batch-location-ping",
    ),
    path(
        "toggle-status/",
        SalesPersonToggleOnlineAPIView.as_view(),
        name="salesperson-toggle-status",
    ),
    path(
        "me/",
        SalesPersonSelfLocationAPIView.as_view(),
        name="salesperson-self-location",
    ),
    # Supervisor / Map dashboard endpoints
    path(
        "salespersons/",
        SalesPersonLocationListAPIView.as_view(),
        name="salesperson-location-list",
    ),
    path(
        "salespersons/<int:pk>/",
        SalesPersonLocationDetailAPIView.as_view(),
        name="salesperson-location-detail",
    ),
    path(
        "salespersons/<int:salesperson_id>/history/",
        SalesPersonLocationHistoryListAPIView.as_view(),
        name="salesperson-history-detail",
    ),
    path(
        "history/",
        SalesPersonLocationHistoryListAPIView.as_view(),
        name="salesperson-history-list",
    ),
]
