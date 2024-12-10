# sales-backend/sales/urls.py
from django.urls import path
from .views import InventoryListView, OrderCreateView, OrderUpdateView

urlpatterns = [
    path('inventory/', InventoryListView.as_view(), name='inventory-list'),
    path('orders/', OrderCreateView.as_view(), name='order-create'),  # URL for creating orders
    path('orders/<int:pk>/', OrderUpdateView.as_view(), name='order-update'),  # URL for updating orders
]