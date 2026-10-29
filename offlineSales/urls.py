from django.urls import path

from offlineSales.views import (
    OfflineCustomerDetailView,
    OfflineCustomerListCreateView,
    OfflineCustomerOrdersListView,
    OfflineOrderCancelView,
    OfflineOrderCreditReminderListView,
    OfflineOrderDetailView,
    OfflineOrderListCreateView,
    OfflinePaymentHistoryDetailView,
    OfflinePaymentHistoryListCreateView,
    OfflineSalesStatsView,
)

urlpatterns = [
    # Overall statistics
    path(
        "stats/",
        OfflineSalesStatsView.as_view(),
        name="offline-sales-stats",
    ),
    # Customer endpoints
    path(
        "customers/",
        OfflineCustomerListCreateView.as_view(),
        name="offline-customer-list-create",
    ),
    path(
        "customers/<int:pk>/",
        OfflineCustomerDetailView.as_view(),
        name="offline-customer-detail",
    ),
    path(
        "customers/<int:customer_id>/orders/",
        OfflineCustomerOrdersListView.as_view(),
        name="offline-customer-orders",
    ),
    # Order endpoints
    path(
        "orders/",
        OfflineOrderListCreateView.as_view(),
        name="offline-order-list-create",
    ),
    # Credit reminder endpoint (must be declared before <str:order_code> to prevent slug clash)
    path(
        "orders/credit-reminders/",
        OfflineOrderCreditReminderListView.as_view(),
        name="offline-order-credit-reminders",
    ),
    path(
        "orders/<str:order_code>/",
        OfflineOrderDetailView.as_view(),
        name="offline-order-detail",
    ),
    path(
        "orders/<str:order_code>/cancel/",
        OfflineOrderCancelView.as_view(),
        name="offline-order-cancel",
    ),
    # Payment endpoints
    path(
        "payments/",
        OfflinePaymentHistoryListCreateView.as_view(),
        name="offline-payment-list-create",
    ),
    path(
        "payments/<int:pk>/",
        OfflinePaymentHistoryDetailView.as_view(),
        name="offline-payment-detail",
    ),
]
