from django.shortcuts import render
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import Inventory, Order,Commission,Product
from .serializers import InventorySerializer, OrderSerializer,ProductSerializer
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User

# Create your views here.

class InventoryListView(generics.ListAPIView):
    serializer_class = InventorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Inventory.objects.filter(distributor=user.distributor)

class OrderListCreateView(generics.ListCreateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user  
        if user.role == 'Distributor':  
            queryset = Order.objects.filter(distributor=user.distributor)  
            return queryset 
        elif user.role == 'SalesPerson': 
            queryset = Order.objects.filter(sales_person=user)  
            return queryset  
        return Order.objects.none()  

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()  
        serializer = self.get_serializer(queryset, many=True)  
        return Response(serializer.data)  

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
        print(f"Order ID: {order.id}")
        
        previous_status = order.order_status  
        
        response = super().update(request, *args, **kwargs)

        order.refresh_from_db()

        if order.order_status == "Delivered" and previous_status != "Delivered":
            
            try:
                distributor_commission = Commission.objects.get(
                    distributor=order.distributor,
                    sales_person=order.sales_person
                )
                print(f"Commission Amount: {distributor_commission.amount}")
                order.commission_amount = distributor_commission.amount
                order.save()  # Save the order with the updated commission amount

                # Update the salesperson's total commission amount
                salesperson = order.sales_person
                salesperson.commission_amount += order.commission_amount
                salesperson.save()  # Save the updated salesperson

                # Optionally, create a commission record
                commission = Commission(sales_person=order.sales_person, distributor=order.distributor, amount=order.commission_amount)
                commission.save()  # Save the commission record
            except Commission.DoesNotExist:
                return Response({"detail": "Commission not set for this salesperson."}, status=status.HTTP_400_BAD_REQUEST)
        
        return response

class CommissionPaymentView(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, salesperson_id):
        """Handle the commission payment for a specific salesperson."""
        distributor = request.user  # The logged-in distributor

        try:
            # Retrieve the salesperson and their commission details
            salesperson = User.objects.get(id=salesperson_id)  # Assuming User is the model for salespersons
            
            # Check if the distributor of the salesperson matches the logged-in distributor
            if salesperson.distributor != distributor:
                return Response({"detail": "You do not have permission to pay this salesperson's commission."}, status=status.HTTP_403_FORBIDDEN)

            commission = Commission.objects.get(distributor=distributor, sales_person=salesperson)

            # Logic to mark the commission as paid
            commission.paid = True  # Assuming there's a 'paid' field in the Commission model
            commission.save()  # Save the updated commission record

            # Optionally, update the salesperson's total commission amount
            salesperson.commission_amount += commission.amount  # Assuming 'amount' is the commission amount
            salesperson.save()  # Save the updated salesperson

            return Response({"detail": "Commission marked as paid."}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({"detail": "Salesperson not found."}, status=status.HTTP_404_NOT_FOUND)
        except Commission.DoesNotExist:
            return Response({"detail": "Commission not found for this salesperson."}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        if order.salesperson != request.user:
            return Response({"detail": "You do not have permission to update this order."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)
    
class ProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    queryset = Product.objects.all()

            
