from django.urls import path

from .views import (
    AssignOrderView,
    ExportOrdersCSVView,
    GetYDMRiderView,
    InvoiceListCreateView,
    InvoiceReportListCreateView,
    InvoiceReportRetrieveUpdateDestroyView,
    InvoiceRetrieveUpdateDestroyView,
    OrderCommentListCreateView,
    OrderCommentRetrieveUpdateDestroyView,
    UpdateOrderStatusView,
    daily_orders_by_franchise,
    franchise_statement_api,
    get_complete_dashboard_stats,
    get_franchise_order_stats,
    get_total_pending_cod,
    track_order,
)

urlpatterns = [
    path("track-order/", track_order, name="track-order"),
    path(
        "logistics/franchise/<int:franchise_id>/order-stats/",
        get_franchise_order_stats,
        name="franchise_stats_function",
    ),
    path(
        "logistics/order-comment/",
        OrderCommentListCreateView.as_view(),
        name="order-comment-list-create",
    ),
    path(
        "logistics/order-comment/<int:pk>/",
        OrderCommentRetrieveUpdateDestroyView.as_view(),
        name="order-comment-detail",
    ),
    path(
        "logistics/franchise/<int:franchise_id>/dashboard-stats/",
        get_complete_dashboard_stats,
        name="complete_dashboard_stats",
    ),
    path(
        "logistics/franchise/<int:franchise_id>/total-pending-cod/",
        get_total_pending_cod,
        name="total_pending_cod",
    ),
    path(
        "logistics/franchise/<int:franchise_id>/daily-stats/",
        daily_orders_by_franchise,
        name="daily_stats_by_franchise",
    ),
    path(
        "logistics/franchise/<int:franchise_id>/statement/",
        franchise_statement_api,
        name="franchise_statement",
    ),
    path("logistics/assign-order/", AssignOrderView.as_view(), name="assign-order"),
    path("logistics/ydm-riders/", GetYDMRiderView.as_view(), name="ydm-rider"),
    path(
        "logistics/update-order-status/",
        UpdateOrderStatusView.as_view(),
        name="update-order-status",
    ),
    path(
        "logistics/export-orders/", ExportOrdersCSVView.as_view(), name="export-orders"
    ),
    path(
        "logistics/invoice/",
        InvoiceListCreateView.as_view(),
        name="invoice-list-create",
    ),
    path(
        "logistics/invoice/<int:pk>/",
        InvoiceRetrieveUpdateDestroyView.as_view(),
        name="invoice-detail",
    ),
    path(
        "logistics/invoice-report/",
        InvoiceReportListCreateView.as_view(),
        name="invoice-report-list-create",
    ),
    path(
        "logistics/invoice-report/<int:pk>/",
        InvoiceReportRetrieveUpdateDestroyView.as_view(),
        name="invoice-report-detail",
    ),
]
