from django.urls import path

from .views import (
    OrderCSVExportView,
    PackagingSentToDashSummaryCSVView,
    SalesPersonOrderCSVExportView,
    SalesSummaryExportView,
    export_orders_csv_api,
)

urlpatterns = [
    path("export-csv/", OrderCSVExportView.as_view(), name="export-csv"),
    path(
        "salesperson/<str:phone_number>/export-orders/",
        SalesPersonOrderCSVExportView.as_view(),
        name="salesperson-export-orders",
    ),
    path("sales-summary/", SalesSummaryExportView.as_view(), name="sales-summary"),
    path(
        "packaging/summary/",
        PackagingSentToDashSummaryCSVView.as_view(),
        name="packaging-summary",
    ),
    path("export-summary/", export_orders_csv_api, name="export-summary"),
]
