from django.urls import path

from .views import (
    YDMLogisticsListCreateView,
    YDMLogisticsRetrieveUpdateDestroyView,
    YDMWebhookAPIView,
)

urlpatterns = [
    path(
        "ydm-logistics/",
        YDMLogisticsListCreateView.as_view(),
        name="ydm-logistics-list-create",
    ),
    path(
        "ydm-logistics/<int:pk>/",
        YDMLogisticsRetrieveUpdateDestroyView.as_view(),
        name="ydm-logistics-detail",
    ),
    path(
        "ydm/webhook/",
        YDMWebhookAPIView.as_view(),
        name="ydm-webhook",
    ),
]
