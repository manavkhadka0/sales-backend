from django.shortcuts import render
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import Inventory, Order
from .serializers import InventorySerializer, OrderSerializer
from rest_framework.response import Response
from rest_framework import status

# Create your views here.

class InventoryListView(generics.ListAPIView):
    serializer_class = InventorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Inventory.objects.filter(distributor=user.distributor)

class OrderCreateView(generics.CreateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        salesperson = self.request.user
        distributor = salesperson.distributor
        serializer.save(sales_person=salesperson, distributor=distributor)

class OrderUpdateView(generics.UpdateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def update(self, request, *args, **kwargs):
        order = self.get_object()
        if order.salesperson != request.user:
            return Response({"detail": "You do not have permission to update this order."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)
