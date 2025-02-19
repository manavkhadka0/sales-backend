from django.shortcuts import render
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import Inventory, Order,Commission,Product,InventoryChangeLog
from account.models import Distributor, Franchise,Factory
from .serializers import InventorySerializer, OrderSerializer,ProductSerializer, OrderDetailSerializer,InventoryChangeLogSerializer,InventoryRequestSerializer
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
                            'quantity': inventory.quantity
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
        if user.role == 'SuperAdmin':
            distributors = Distributor.objects.prefetch_related('inventory')
            inventory_summary = []
            for distributor in distributors:
                distributor_inventory = {
                    distributor.name: {
                        'inventory': [
                            {
                                'product': inventory.product.name,
                                'quantity': inventory.quantity
                            } for inventory in distributor.inventory.all()
                        ],
                        'franchises': {}
                    }
                }
                # Get franchises associated with the distributor
                franchises = Franchise.objects.filter(distributor=distributor)
                for franchise in franchises:
                    distributor_inventory[distributor.name]['franchises'][franchise.name] = [
                        {
                            'product': inventory.product.name,
                            'quantity': inventory.quantity
                        } for inventory in franchise.inventory.all()
                    ]
                inventory_summary.append(distributor_inventory)
            return Response(inventory_summary)
        return Inventory.objects.none()

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
            queryset = Order.objects.filter(distributor=user.distributor).order_by('-id')
            return queryset 
        elif user.role == 'SalesPerson': 
            queryset = Order.objects.filter(sales_person=user).order_by('-id')
            return queryset  
        elif user.role == 'SuperAdmin':  
            queryset = Order.objects.all().order_by('-id')
            return queryset
        return Order.objects.all().order_by('-id')

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

class InventoryRequestView(generics.CreateAPIView):
    queryset = Inventory.objects.all()
    serializer_class = InventoryRequestSerializer
    # permission_classes = [IsAuthenticated]


    def perform_create(self, serializer):
        # Set the user who is logged in as the creator of the InventoryRequest
        serializer.save(user=self.request.user)

# Return an empty queryset for non-Distributor users