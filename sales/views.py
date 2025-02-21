from django.shortcuts import render
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import Inventory, Order,Commission,Product,InventoryChangeLog,InventoryRequest
from account.models import Distributor, Franchise,Factory
from .serializers import InventorySerializer, OrderSerializer,ProductSerializer, OrderDetailSerializer,InventoryChangeLogSerializer,InventoryRequestSerializer
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from django_filters import rest_framework as django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters as rest_filters
from rest_framework.pagination import PageNumberPagination
from rest_framework import serializers

# Create your views here.

class InventoryListView(generics.ListAPIView):
    serializer_class = InventorySerializer
    # permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'Franchise':  # Only get inventory for Franchise users
            return Inventory.objects.filter(franchise=user.franchise)  # Franchise can see their own inventory
        return Inventory.objects.none()  # Return an empty queryset for other roles

    def list(self, request, *args, **kwargs):
        user = self.request.user
        print(user.role)
        if user.role == 'SuperAdmin':
            # Get all factories and their inventories
            factories = Factory.objects.prefetch_related('inventory')
            inventory_summary = {}
            for factory in factories:
                inventory_summary[factory.name] = {
                    'inventory': [
                        {
                            'product': inventory.product.name,
                            'quantity': inventory.quantity
                        } for inventory in factory.inventory.all()
                    ],
                    'distributors': {}
                }
                # Get distributors associated with the factory
                distributors = Distributor.objects.prefetch_related('inventory')
                for distributor in distributors:
                    inventory_summary[factory.name]['distributors'][distributor.name] = {
                        'inventory': [
                            {
                                'product': inventory.product.name,
                                'quantity': inventory.quantity
                            } for inventory in distributor.inventory.all()
                        ],
                        'franchises': {}
                    }
                    # Get franchises associated with the distributor
                    franchises = Franchise.objects.filter(distributor=distributor)
                    for franchise in franchises:
                        inventory_summary[factory.name]['distributors'][distributor.name]['franchises'][franchise.name] = [
                            {
                                'product': inventory.product.name,
                                'quantity': inventory.quantity
                            } for inventory in franchise.inventory.all()
                        ]
            return Response(inventory_summary)  # Return the summary for SuperAdmin
        elif user.role == 'Distributor':
            # Get the distributor's inventory
            inventory_summary = {
                user.distributor.name: {
                    'inventory': [
                        {
                            'product': inventory.product.name,
                            'quantity': inventory.quantity
                        } for inventory in user.distributor.inventory.all()
                    ],
                    'franchises': {}
                }
            }
            # Get franchises associated with the distributor
            franchises = Franchise.objects.filter(distributor=user.distributor)
            for franchise in franchises:
                inventory_summary[user.distributor.name]['franchises'][franchise.name] = [
                    {
                        'product': inventory.product.name,
                        'quantity': inventory.quantity
                    } for inventory in franchise.inventory.all()
                ]
            return Response(inventory_summary)  # Return the summary for Distributor
        elif user.role == 'Franchise':  # Added handling for Franchise role
            # Get the franchise's inventory
            print(user.franchise.inventory.all())
            inventory_summary = {
                user.franchise.name: {
                    'inventory': [
                        {
                            'id': inventory.id,
                            'product': inventory.product.name,
                            'quantity': inventory.quantity
                        } for inventory in user.franchise.inventory.all()
                    ]
                }
            }
            return Response(inventory_summary) # Return the summary for Franchise
        else:
            # Call the superclass's list method for other roles
            return super().list(request, *args, **kwargs)

class FactoryInventoryListView(generics.ListAPIView):
    serializer_class = InventorySerializer
    queryset = Inventory.objects.all()

    def list(self, request, *args, **kwargs):
        user = self.request.user
        if user.role == 'SuperAdmin':
            # Get all factories and their inventories
            factories = Factory.objects.prefetch_related('inventory')
            inventory_summary = []
            for factory in factories:
                inventory_summary.append({
                    'factory': factory.name,
                    'inventory': [
                        {
                            'product': inventory.product.name,
                            'quantity': inventory.quantity,

                        } for inventory in factory.inventory.all()
                    ]
                })
            return Response(inventory_summary)  # Return the summary for SuperAdmin
        
        return Inventory.objects.none()  # Return an empty queryset for non-SuperAdmin users

class DistributorInventoryListView(generics.ListAPIView):
    serializer_class = InventorySerializer
    queryset = Inventory.objects.all()

    def list(self, request, *args, **kwargs):
        user = self.request.user
        print(user.role)
        if user.role == 'SuperAdmin':
            distributors = Distributor.objects.prefetch_related('inventory')
            inventory_summary = {}  # Changed from list to dictionary
            for distributor in distributors:
                distributor_inventory = {
                    'inventory': [
                        {
                            'product': inventory.product.name,
                            'quantity': inventory.quantity
                        } for inventory in distributor.inventory.all()
                    ],
                    'franchises': {}
                }
                franchises = Franchise.objects.filter(distributor=distributor)
                for franchise in franchises:
                    distributor_inventory['franchises'][franchise.name] = [  # Accessing the correct dictionary
                        {
                            'product': inventory.product.name,
                            'quantity': inventory.quantity
                        } for inventory in franchise.inventory.all()
                    ]
                inventory_summary[distributor.name] = distributor_inventory  # Store in the dictionary
            return Response(inventory_summary)
        elif user.role == 'Distributor':
            # Get the distributor's inventory
            inventory_summary = {
                user.distributor.name: {
                    'inventory': [
                        {
                            'product': inventory.product.name,
                            'quantity': inventory.quantity
                        } for inventory in user.distributor.inventory.all()
                    ],
                    'franchises': {}
                }
            }
            # Get franchises associated with the distributor
            franchises = Franchise.objects.filter(distributor=user.distributor)
            for franchise in franchises:
                inventory_summary[user.distributor.name]['franchises'][franchise.name] = [
                    {
                        'product': inventory.product.name,
                        'quantity': inventory.quantity
                    } for inventory in franchise.inventory.all()
                ]
            return Response(inventory_summary)
        elif user.role == 'Franchise':  # Added handling for Franchise role
            # Get the franchise's inventory
            inventory_summary = {
                user.franchise.name: {
                    'inventory': [
                        {
                            'product': inventory.product.name,
                            'quantity': inventory.quantity
                        } for inventory in user.franchise.inventory.all()
                    ]
                }
            }
            return Response(inventory_summary)  # Return the summary for Franchise
        return Response([])  # Return an empty Response for non-SuperAdmin users

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
    queryset = Order.objects.all().order_by('-id')
    serializer_class = OrderSerializer
    # permission_classes = [IsAuthenticated]
    filterset_class = OrderFilter
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter,rest_filters.OrderingFilter]  # Added SearchFilter
    search_fields = ['phone_number', 'sales_person__username']  # Specify the fields to search
    ordering_fields = ['-id',]
    pagination_class = CustomPagination

    def get_queryset(self):
        user = self.request.user  
        if user.role == 'Distributor':  
            # Get orders from all franchises under this distributor
            franchises = Franchise.objects.filter(distributor=user.distributor)
            queryset = Order.objects.filter(franchise__in=franchises).order_by('-id')
            return queryset 
        elif user.role == 'SalesPerson': 
            # Get orders where the user is the sales person
            queryset = Order.objects.filter(sales_person=user).order_by('-id')
            return queryset  
        elif user.role == 'Franchise':
            # Get orders for this franchise
            queryset = Order.objects.filter(franchise=user.franchise).order_by('-id')
            return queryset
        elif user.role == 'SuperAdmin':  
            # SuperAdmin can see all orders
            queryset = Order.objects.all().order_by('-id')
            return queryset
        else:
            return Order.objects.none()  # Return empty queryset for unknown roles

    def perform_create(self, serializer):
        salesperson = self.request.user
        franchise = salesperson.franchise
        
        # Validate inventory before creating order
        order_products_data = self.request.data.get('order_products', [])
        for order_product_data in order_products_data:
            inventory_id = order_product_data['product_id']
            quantity = order_product_data['quantity']

            try:
                inventory_item = Inventory.objects.get(
                    id=inventory_id,
                    franchise=franchise  # Ensure the inventory belongs to the franchise
                )
                if inventory_item.quantity < quantity:
                    raise serializers.ValidationError(
                        f"Insufficient inventory for product {inventory_item.product.name}. "
                        f"Available: {inventory_item.quantity}, Requested: {quantity}"
                    )
            except Inventory.DoesNotExist:
                raise serializers.ValidationError(
                    f"Inventory item with ID {inventory_id} not found in franchise inventory"
                )

        # Create order if validation passes
        order = serializer.save(sales_person=salesperson, franchise=franchise)

        # Update inventory quantities
        for order_product_data in order_products_data:
            inventory_id = order_product_data['product_id']
            quantity = order_product_data['quantity']

            inventory_item = Inventory.objects.get(id=inventory_id)
            inventory_item.quantity -= quantity
            inventory_item.save()

        return order

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
                order.commission_amount = (distributor_commission.rate / 100) * order.total_amount  # Calculate commission based on total amount
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

    
class ProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == 'Franchise' or user.role == 'SalesPerson':
            # Get products and their inventory IDs from franchise's inventory
            franchise_inventory = Inventory.objects.filter(franchise=user.franchise).values(
                'id', 
                'product', 
                'product__name',
                'quantity'
            )
            product_list = []
            for inv in franchise_inventory:
                product_list.append({
                    'inventory_id': inv['id'],
                    'product_id': inv['product'],
                    'product_name': inv['product__name'],
                    'quantity': inv['quantity']
                })
            return product_list
        elif user.role == 'Distributor':
            # Get products and their inventory IDs from distributor's inventory
            distributor_inventory = Inventory.objects.filter(distributor=user.distributor).values(
                'id', 
                'product', 
                'product__name',
                'quantity'
            )
            product_list = []
            for inv in distributor_inventory:
                product_list.append({
                    'inventory_id': inv['id'],
                    'product_id': inv['product'],
                    'product_name': inv['product__name'],
                    'quantity': inv['quantity']
                })
            return product_list
        elif user.role == 'SuperAdmin':
            # SuperAdmin can see all products
            return Product.objects.all()
        return Product.objects.none()  # Return empty queryset for other roles

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if isinstance(queryset, list):  # If it's our custom product list
            return Response(queryset)
        # Otherwise, use default serializer behavior
        return super().list(request, *args, **kwargs)

class InventoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Inventory.objects.all()
    serializer_class = InventorySerializer
    # permission_classes = [IsAuthenticated]

    def perform_update(self, serializer):
        inventory_item = self.get_object()
        
        # Retrieve the new quantity from the request data
        new_quantity = self.request.data.get('new_quantity')        
        # Create a log entry before updating
        InventoryChangeLog.objects.create(
            inventory=inventory_item,
            old_quantity=inventory_item.quantity,
            new_quantity=new_quantity if new_quantity is not None else inventory_item.quantity
        )
        
        # Update the inventory item's quantity if new_quantity is provided
        if new_quantity is not None:  # Check if new_quantity is provided
            inventory_item.quantity = new_quantity
        
        # Save the updated inventory item using the serializer
        serializer.save(quantity=inventory_item.quantity)  # Pass the updated quantity to the serializer


class InventoryChangeLogView(generics.ListAPIView):
    serializer_class = InventoryChangeLogSerializer
    queryset = InventoryChangeLog.objects.all()

    def get_queryset(self):
        # Use 'pk' instead of 'id'
        inventory_pk = self.kwargs.get('pk')
        if inventory_pk is not None:
            logs = InventoryChangeLog.objects.filter(inventory__id=inventory_pk)  # Filter by inventory PK
            return logs
        return InventoryChangeLog.objects.none()  # Return an empty queryset if 'pk' is not provided

class Inventorylogs(generics.ListAPIView):
    serializer_class = InventoryChangeLogSerializer
    queryset = InventoryChangeLog.objects.all()

class InventoryRequestView(generics.ListCreateAPIView):
    queryset = InventoryRequest.objects.all()
    serializer_class = InventoryRequestSerializer

    def perform_create(self, serializer):
        # The user will be set in the serializer's create method
        serializer.save()

class InventoryRequestDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = InventoryRequest.objects.all()
    serializer_class = InventoryRequestSerializer
    # permission_classes = [IsAuthenticated]

    def patch(self, request, *args, **kwargs):
        partial = True  # Allow partial updates
        return self.update(request, *args, partial=partial, **kwargs)

    def perform_update(self, serializer):
        # Update the total_amount and status if provided in the request data
        total_amount = self.request.data.get('total_amount')
        status = self.request.data.get('status')

        if total_amount is not None:
            serializer.instance.total_amount = total_amount
        if status is not None:
            serializer.instance.status = status

        serializer.save()  # Save the updated instance 