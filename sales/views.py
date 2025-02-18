from django.shortcuts import render
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import Inventory, Order,Commission,Product
from .serializers import InventorySerializer, OrderSerializer,ProductSerializer, OrderDetailSerializer
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from django_filters import rest_framework as django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters as rest_filters
from rest_framework.pagination import PageNumberPagination

# Create your views here.

class InventoryListView(generics.ListAPIView):
    serializer_class = InventorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Inventory.objects.filter(distributor=user.distributor)
class CustomPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class OrderFilter(django_filters.FilterSet):
    distributor = django_filters.CharFilter(field_name="distributor__id", lookup_expr='exact')
    sales_person = django_filters.CharFilter(field_name="sales_person__id", lookup_expr='exact')
    order_status = django_filters.CharFilter(field_name="order_status", lookup_expr='icontains')
    city=django_filters.CharFilter(field_name="city", lookup_expr='icontains')
    date=django_filters.DateFilter(field_name="date", lookup_expr='exact')
    gte_date=django_filters.DateFilter(field_name="date", lookup_expr='gte')
    lte_date=django_filters.DateFilter(field_name="date", lookup_expr='lte')

    class Meta:
        model = Order
        fields = ['distributor', 'sales_person', 'order_status', 'date', 'gte_date', 'lte_date', 'city']

class OrderListCreateView(generics.ListCreateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    # permission_classes = [IsAuthenticated]  
    filterset_class = OrderFilter
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter,rest_filters.OrderingFilter]  # Added SearchFilter
    search_fields = ['phone_number', 'sales_person__username']  # Specify the fields to search
    ordering_fields = ['date',]
    pagination_class = CustomPagination

    def get_queryset(self):
        user = self.request.user  
        if user.role == 'Distributor':  
            queryset = Order.objects.filter(distributor=user.distributor)  
            return queryset 
        elif user.role == 'SalesPerson': 
            queryset = Order.objects.filter(sales_person=user)  
            return queryset  
        elif user.role == 'SuperAdmin':  
            queryset = Order.objects.all()  
            return queryset
        return Order.objects.all()

    def perform_create(self, serializer):
        salesperson = self.request.user
        distributor = salesperson.distributor
        
        # Check if the phone number already exists in any order
        phone_number = self.request.data.get('phone_number')
        existing_order = Order.objects.filter(phone_number=phone_number).first()
        
        if existing_order:
            # If an existing order is found, return a message with details
            order_detail_serializer = OrderDetailSerializer(existing_order)
            return Response({
                "detail": "This phone number is already associated with an existing order.",
                "order": order_detail_serializer.data
            }, status=status.HTTP_400_BAD_REQUEST)

        order = serializer.save(sales_person=salesperson, distributor=distributor)

        # Reduce the quantity in the Inventory model
        order_products_data = self.request.data.get('order_products', [])
        for order_product_data in order_products_data:
            product_id = order_product_data['product_id']
            quantity = order_product_data['quantity']

            # Get the corresponding Inventory item
            try:
                inventory_item = Inventory.objects.get(distributor=distributor, product_id=product_id)
                inventory_item.quantity -= quantity
                inventory_item.save()  # Save the updated inventory item
            except Inventory.DoesNotExist:
                # Handle the case where the inventory item does not exist
                raise Exception(f"Inventory item for product ID {product_id} not found for distributor {distributor.id}.")

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
                print(f"Commission Rate: {distributor_commission.rate}")  # Changed from amount to rate
                
                # Calculate total amount from order products
                total_amount = sum(order_product.get_total_price() for order_product in order.order_products.all())  # Assuming order_products is a related name

                order.commission_amount = (distributor_commission.rate / 100) * total_amount  # Calculate commission based on total amount
                order.save()  # Save the order with the updated commission amount

                # Update the salesperson's total commission amount
                salesperson = order.sales_person
                salesperson.commission_amount += order.commission_amount
                salesperson.save()  # Save the updated salesperson

                # # Optionally, create a commission record
                # commission = Commission(sales_person=order.sales_person, distributor=order.distributor, rate=order.commission_amount)
                # commission.save()  # Save the commission record
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

            
