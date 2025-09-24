from django.urls import path

from .views import (
    FestConfigListCreateView,
    FestConfigRetrieveUpdateDestroyView,
    SalesGroupDetailView,
    SalesGroupListCreateView,
    SalesGroupStatsView,
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
        FestConfigListCreateView.as_view(),
        name="festconfig-list-create",
    ),
    path(
        "fest-config/<int:franchise_id>/",
        FestConfigRetrieveUpdateDestroyView.as_view(),
        name="festconfig-detail",
    ),
    path(
        "sales-group-stats/",
        SalesGroupStatsView.as_view(),
        name="salesgroup-stats",
    ),
]
