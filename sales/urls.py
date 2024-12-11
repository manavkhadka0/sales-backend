# sales-backend/sales/urls.py
from django.urls import path
from .views import InventoryListView, OrderCreateView, OrderUpdateView,CommissionPaymentView

urlpatterns = [
    path('inventory/', InventoryListView.as_view(), name='inventory-list'),
    path('orders/', OrderCreateView.as_view(), name='order-create'),  # URL for creating orders
    path('orders/<int:pk>/', OrderUpdateView.as_view(), name='order-update'),  # URL for updating orders
    path('commission/payment/<int:salesperson_id>/', CommissionPaymentView.as_view(), name='commission-payment'),

]