from django.urls import path

from .views import (
    FestConfigRetrieveUpdateView,
    SalesGroupDetailView,
    SalesGroupListCreateView,
)

urlpatterns = [
    path(
        "sales-groups/",
        SalesGroupListCreateView.as_view(),
        name="salesgroup-list-create",
    ),
    path(
        "sales-groups/<int:pk>/",
        SalesGroupDetailView.as_view(),
        name="salesgroup-detail",
    ),
    path(
        "fest-config/",
        FestConfigRetrieveUpdateView.as_view(),
        name="fest-config",
    ),
]
