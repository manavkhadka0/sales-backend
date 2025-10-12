# sales-backend/sales/urls.py
from django.urls import path

from .views import (
    AllProductsListView,
    CommissionPaymentView,
    CurrentDatabaseModeView,
    DistributorInventoryListView,
    FactoryInventoryListView,
    FranchiseInventoryListView,
    InventoryChangeLogView,
    InventoryCheckView,
    InventoryDateSnapshotView,
    InventoryDetailView,
    InventoryListCreateView,
    Inventorylogs,
    InventoryRequestDetailView,
    InventoryRequestView,
    LocationSearchAPIView,
    LocationUploadView,
    OrderDetailUpdateView,
    OrderListCreateView,
    OrderUpdateView,
    ProductListView,
    PromoCodeDetailView,
    PromoCodeListCreateView,
    RawMaterialListView,
    UserInventoryLogs,
    ValidatePromoCodeView,
    switch_db,
)

urlpatterns = [
    path("inventory/", InventoryListCreateView.as_view(), name="inventory-list"),
    path(
        "factory-inventory/",
        FactoryInventoryListView.as_view(),
        name="factory-inventory-list",
    ),
    path(
        "distributor-inventory/",
        DistributorInventoryListView.as_view(),
        name="distributor-inventory-list",
    ),
    path(
        "franchise-inventory/",
        FranchiseInventoryListView.as_view(),
        name="franchise-inventory-list",
    ),
    path(
        "inventory/<int:pk>/", InventoryDetailView.as_view(), name="inventory-detail"
    ),  # Detail, update, delete view
    path(
        "inventory/<int:pk>/log/",
        InventoryChangeLogView.as_view(),
        name="inventory-log",
    ),  # Updated to include 'id'
    path(
        "inventory-request/", InventoryRequestView.as_view(), name="inventory-request"
    ),
    path(
        "inventory-request/<int:pk>/",
        InventoryRequestDetailView.as_view(),
        name="inventory-request-detail",
    ),
    path(
        "inventory-date-product/",
        InventoryDateSnapshotView.as_view(),
        name="inventory-date-product",
    ),
    path("log/", Inventorylogs.as_view(), name="log"),
    path(
        "user-inventory-logs/", UserInventoryLogs.as_view(), name="user-inventory-logs"
    ),
    path(
        "orders/", OrderListCreateView.as_view(), name="order-create"
    ),  # URL for creating orders
    path(
        "orders/<int:pk>/update/", OrderDetailUpdateView.as_view(), name="order-update"
    ),
    path(
        "orders/<int:pk>/", OrderUpdateView.as_view(), name="order-update"
    ),  # URL for updating orders
    path(
        "commission/payment/<int:salesperson_id>/",
        CommissionPaymentView.as_view(),
        name="commission-payment",
    ),
    path("products/", ProductListView.as_view(), name="product-list"),
    path("all-products/", AllProductsListView.as_view(), name="all-products-list"),
    path("raw-materials/", RawMaterialListView.as_view(), name="raw-materials"),
    path("inventory-check/", InventoryCheckView.as_view(), name="inventory-check"),
    path("promo-codes/", PromoCodeListCreateView.as_view(), name="promo-code-list"),
    path(
        "promo-codes/<int:pk>/", PromoCodeDetailView.as_view(), name="promo-code-detail"
    ),
    path(
        "validate-promo-code/",
        ValidatePromoCodeView.as_view(),
        name="validate-promo-code",
    ),
    path("locations/", LocationSearchAPIView.as_view(), name="location-search"),
    path("upload-locations/", LocationUploadView.as_view(), name="upload-locations"),
    path("switch-db/", switch_db),
    path(
        "current-database/", CurrentDatabaseModeView.as_view(), name="current-database"
    ),
]
