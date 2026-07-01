from django.urls import path

from .views import (
    CancelDarazOrderView,
    DarazLocationImportView,
    DarazLocationListView,
    GetDarazConfigView,
    SendOrderToDarazView,
)

urlpatterns = [
    path(
        "orders/<int:order_id>/send/",
        SendOrderToDarazView.as_view(),
        name="daraz-send-order",
    ),
    path(
        "orders/<int:order_id>/cancel/",
        CancelDarazOrderView.as_view(),
        name="daraz-cancel-order",
    ),
    path(
        "config/",
        GetDarazConfigView.as_view(),
        name="daraz-get-config",
    ),
    path(
        "locations/",
        DarazLocationListView.as_view(),
        name="daraz-location-list",
    ),
    path(
        "locations/import/",
        DarazLocationImportView.as_view(),
        name="daraz-location-import",
    ),
]
