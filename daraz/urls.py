from django.urls import path

from .views import GetDarazConfigView, SaveDarazTokenView, SendOrderToDarazView

urlpatterns = [
    path(
        "orders/<int:order_id>/send/",
        SendOrderToDarazView.as_view(),
        name="daraz-send-order",
    ),
    path(
        "save-token/",
        SaveDarazTokenView.as_view(),
        name="daraz-save-token",
    ),
    path(
        "config/",
        GetDarazConfigView.as_view(),
        name="daraz-get-config",
    ),
]
