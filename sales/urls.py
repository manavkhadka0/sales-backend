# sales-backend/sales/urls.py
from django.urls import path
from .views import InventoryListView, OrderListCreateView, OrderUpdateView,CommissionPaymentView,ProductListView,InventoryDetailView,InventoryChangeLogView,Inventorylogs,FactoryInventoryListView,DistributorInventoryListView,InventoryRequestView,InventoryRequestDetailView,AllProductsListView
    
urlpatterns = [
    path('inventory/', InventoryListView.as_view(), name='inventory-list'),
    path('factory-inventory/', FactoryInventoryListView.as_view(), name='factory-inventory-list'),
    path('distributor-inventory/', DistributorInventoryListView.as_view(), name='distributor-inventory-list'),
    path('inventory/<int:pk>/', InventoryDetailView.as_view(), name='inventory-detail'),  # Detail, update, delete view
    path('inventory/<int:pk>/log/', InventoryChangeLogView.as_view(), name='inventory-log'),  # Updated to include 'id'
    path('inventory-request/', InventoryRequestView.as_view(), name='inventory-request'),
    path('inventory-request/<int:pk>/', InventoryRequestDetailView.as_view(), name='inventory-request-detail'),
    
    path('log/',Inventorylogs.as_view(),name='log'),
    path('orders/', OrderListCreateView.as_view(), name='order-create'),  # URL for creating orders
    path('orders/<int:pk>/', OrderUpdateView.as_view(), name='order-update'),  # URL for updating orders
    path('commission/payment/<int:salesperson_id>/', CommissionPaymentView.as_view(), name='commission-payment'),
    path('products/', ProductListView.as_view(), name='product-list'),
    path('all-products/', AllProductsListView.as_view(), name='all-products-list'),



]