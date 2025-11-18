# sales/urls.py
from django.urls import path

from .views import (
    FetchAndSavePicknDropBranches,
    PickNDropListCreateView,
    PickNDropWebhookView,
    SendOrderToPicknDropByIdView,
)

urlpatterns = [
    path(
        "pickndrop/",
        PickNDropListCreateView.as_view(),
        name="pickndrop",
    ),
    path(
        "fetch-pickndrop-location/",
        FetchAndSavePicknDropBranches.as_view(),
        name="fetch_pickndrop_location",
    ),
    path(
        "send-pickndrop/<int:order_id>/",
        SendOrderToPicknDropByIdView.as_view(),
        name="send_pickndrop",
    ),
    path(
        "pickndrop/webhook/", PickNDropWebhookView.as_view(), name="pickndrop-webhook"
    ),
]
