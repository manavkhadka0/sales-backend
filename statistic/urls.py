from django.urls import path

from .views import (
    BulkOrdersView,
    DashboardStatsView,
    LatestOrdersView,
    RevenueByProductView,
    RevenueView,
    RevenueWithCancelledView,
    SalesPersonRevenueView,
    SalesPersonStatisticsView,
    SalesStatisticsView,
    TopProductsView,
    TopSalespersonView,
)

urlpatterns = [
    path("latest-orders/", LatestOrdersView.as_view(), name="latest-orders"),
    path("statistics/", SalesStatisticsView.as_view(), name="sales-statistics"),
    path("top-salespersons/", TopSalespersonView.as_view(), name="top-salespersons"),
    path("revenue/", RevenueView.as_view(), name="revenue"),
    path(
        "revenue-with-cancelled/",
        RevenueWithCancelledView.as_view(),
        name="revenue-with-cancelled",
    ),
    path("top-products/", TopProductsView.as_view(), name="top-products"),
    path("dashboard-stats/", DashboardStatsView.as_view(), name="dashboard-stats"),
    path(
        "revenue-by-product/", RevenueByProductView.as_view(), name="revenue-by-product"
    ),
    path(
        "salesperson/<str:phone_number>/statistics/",
        SalesPersonStatisticsView.as_view(),
        name="salesperson-statistics",
    ),
    path(
        "salesperson/<str:phone_number>/revenue/",
        SalesPersonRevenueView.as_view(),
        name="salesperson-revenue",
    ),
    path("bulk-orders/", BulkOrdersView.as_view(), name="bulk-orders"),
]
