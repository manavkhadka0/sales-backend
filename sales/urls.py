# sales-backend/sales/urls.py
from django.urls import path
from .views import FranchiseInventoryListView, InventoryCheckView, InventoryListCreateView, LatestOrdersView, OrderDetailUpdateView, OrderListCreateView, OrderUpdateView, CommissionPaymentView, ProductListView, InventoryDetailView, InventoryChangeLogView, Inventorylogs, FactoryInventoryListView, DistributorInventoryListView, InventoryRequestView, InventoryRequestDetailView, AllProductsListView, RawMaterialListView, RevenueWithCancelledView, SalesPersonRevenueView, SalesStatisticsView, UserInventoryLogs, TopSalespersonView, RevenueView, TopProductsView, DashboardStatsView, RevenueByProductView, OrderCSVExportView, PromoCodeListCreateView, ValidatePromoCodeView, PromoCodeDetailView, SalesPersonStatisticsView, LocationUploadView, LocationSearchAPIView, SalesPersonOrderCSVExportView, SendOrderToDashByIdView

urlpatterns = [
    path('inventory/', InventoryListCreateView.as_view(), name='inventory-list'),
    path('factory-inventory/', FactoryInventoryListView.as_view(),
         name='factory-inventory-list'),
    path('distributor-inventory/', DistributorInventoryListView.as_view(),
         name='distributor-inventory-list'),
    path('franchise-inventory/', FranchiseInventoryListView.as_view(),
         name='franchise-inventory-list'),
    path('inventory/<int:pk>/', InventoryDetailView.as_view(),
         name='inventory-detail'),  # Detail, update, delete view
    path('inventory/<int:pk>/log/', InventoryChangeLogView.as_view(),
         name='inventory-log'),  # Updated to include 'id'
    path('inventory-request/', InventoryRequestView.as_view(),
         name='inventory-request'),
    path('inventory-request/<int:pk>/',
         InventoryRequestDetailView.as_view(), name='inventory-request-detail'),

    path('log/', Inventorylogs.as_view(), name='log'),
    path('user-inventory-logs/', UserInventoryLogs.as_view(),
         name='user-inventory-logs'),
    path('orders/', OrderListCreateView.as_view(),
         name='order-create'),  # URL for creating orders
    path('orders/<int:pk>/update/',
         OrderDetailUpdateView.as_view(), name='order-update'),
    path('orders/<int:pk>/', OrderUpdateView.as_view(),
         name='order-update'),  # URL for updating orders
    path('latest-orders/', LatestOrdersView.as_view(), name='latest-orders'),

    path('commission/payment/<int:salesperson_id>/',
         CommissionPaymentView.as_view(), name='commission-payment'),
    path('products/', ProductListView.as_view(), name='product-list'),
    path('all-products/', AllProductsListView.as_view(), name='all-products-list'),
    path('statistics/', SalesStatisticsView.as_view(), name='sales-statistics'),

    path('top-salespersons/', TopSalespersonView.as_view(),
         name='top-salespersons'),  # New URL for top salespersons
    path('revenue/', RevenueView.as_view(), name='revenue'),
    path('revenue-with-cancelled/', RevenueWithCancelledView.as_view(),
         name='revenue-with-cancelled'),
    path('top-products/', TopProductsView.as_view(), name='top-products'),
    path('raw-materials/', RawMaterialListView.as_view(), name='raw-materials'),
    path('dashboard-stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('revenue-by-product/', RevenueByProductView.as_view(),
         name='revenue-by-product'),
    path('inventory-check/', InventoryCheckView.as_view(), name='inventory-check'),

    path('export-csv/', OrderCSVExportView.as_view(), name='export-csv'),
    path('promo-codes/', PromoCodeListCreateView.as_view(), name='promo-code-list'),
    path('promo-codes/<int:pk>/', PromoCodeDetailView.as_view(),
         name='promo-code-detail'),
    path('validate-promo-code/', ValidatePromoCodeView.as_view(),
         name='validate-promo-code'),
    path('salesperson/<str:phone_number>/statistics/',
         SalesPersonStatisticsView.as_view(), name='salesperson-statistics'),
    path('salesperson/<str:phone_number>/revenue/',
         SalesPersonRevenueView.as_view(), name='salesperson-revenue'),
    path('locations/', LocationSearchAPIView.as_view(), name='location-search'),
    path('upload-locations/', LocationUploadView.as_view(), name='upload-locations'),
    path('salesperson/<str:phone_number>/export-orders/',
         SalesPersonOrderCSVExportView.as_view(), name='salesperson-export-orders'),

    path('send-order/<int:order_id>/', SendOrderToDashByIdView.as_view(),
         name='send-order-to-dash-by-id'),
]
