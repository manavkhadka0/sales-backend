from django.forms import DecimalField
from django.shortcuts import render
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from account.serializers import UserSmallSerializer
from .models import Inventory, Order,Commission,Product,InventoryChangeLog,InventoryRequest, OrderProduct
from account.models import CustomUser, Distributor, Franchise,Factory
from .serializers import InventorySerializer, OrderSerializer,ProductSerializer,InventoryChangeLogSerializer,InventoryRequestSerializer, TopSalespersonSerializer
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from django_filters import rest_framework as django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters as rest_filters
from rest_framework.pagination import PageNumberPagination
from rest_framework import serializers
from django.utils import timezone
from django.db.models import Count, Sum
from django.db import models
from django.db.models.functions import TruncMonth, TruncWeek, TruncYear


# Create your views here.

class InventoryListCreateView(generics.ListCreateAPIView):
    serializer_class = InventorySerializer
    # permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        user = self.request.user
        if user.role == 'SuperAdmin':
            # Get all factories and their inventories
            factories = Factory.objects.prefetch_related('inventory')
            inventory_summary = {}
            for factory in factories:
                inventory_summary[factory.name] = {
                    'id': factory.id,
                    'inventory': [
                        {
                            'id': inventory.id,
                            'product_id': inventory.product.id,
                            'product': inventory.product.name,
                            'quantity': inventory.quantity,
                            'status': inventory.status
                        } for inventory in factory.inventory.all()
                    ],
                    'distributors': {}
                }
                # Get distributors associated with the factory
                distributors = Distributor.objects.prefetch_related('inventory')
                for distributor in distributors:
                    inventory_summary[factory.name]['distributors'][distributor.name] = {
                        'id': distributor.id,
                        'inventory': [
                            {
                                'id': inventory.id,
                                'product_id': inventory.product.id,
                                'product': inventory.product.name,
                                'quantity': inventory.quantity,
                                'status': inventory.status
                            } for inventory in distributor.inventory.all()
                        ],
                        'franchises': {}
                    }
                    # Get franchises associated with the distributor
                    franchises = Franchise.objects.filter(distributor=distributor)
                    for franchise in franchises:
                        inventory_summary[factory.name]['distributors'][distributor.name]['franchises'][franchise.name] = {
                            'id': franchise.id,
                            'inventory': [
                                {
                                    'id': inventory.id,
                                    'product_id': inventory.product.id,
                                    'product': inventory.product.name,
                                    'quantity': inventory.quantity,
                                    'status': inventory.status
                                } for inventory in franchise.inventory.all()
                            ]
                        }
            return Response(inventory_summary)  # Return the summary for SuperAdmin
        elif user.role == 'Distributor':
            # Get the distributor's inventory
            inventory_summary = {
                user.distributor.name: {
                    'id': user.distributor.id,
                    'inventory': [
                        {
                            'id': inventory.id,
                            'product_id': inventory.product.id,
                            'product': inventory.product.name,
                            'quantity': inventory.quantity,
                            'status': inventory.status
                        } for inventory in user.distributor.inventory.all()
                    ],
                    'franchises': {}
                }
            }
            # Get franchises associated with the distributor
            franchises = Franchise.objects.filter(distributor=user.distributor)
            for franchise in franchises:
                inventory_summary[user.distributor.name]['franchises'][franchise.name] = {
                    'id': franchise.id,
                    'inventory': [
                        {
                            'id': inventory.id,
                            'product_id': inventory.product.id,
                            'product': inventory.product.name,
                            'quantity': inventory.quantity,
                            'status': inventory.status
                        } for inventory in franchise.inventory.all()
                    ]
                }
            return Response(inventory_summary)  # Return the summary for Distributor
        elif user.role == 'Franchise' or user.role == 'SalesPerson':  # Added handling for Franchise role
            # Get the franchise's inventory
            inventory_summary = {
                user.franchise.name: {
                    'id': user.franchise.id,
                    'inventory': [
                        {
                            'id': inventory.id,
                            'product_id': inventory.product.id,
                            'product': inventory.product.name,
                            'quantity': inventory.quantity,
                            'status': inventory.status
                        } for inventory in user.franchise.inventory.all()
                    ]
                }
            }
            return Response(inventory_summary) # Return the summary for Franchise
        else:
            # Call the superclass's list method for other roles
            return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        user = self.request.user
        product = serializer.validated_data['product']
        quantity = serializer.validated_data['quantity']
        status = serializer.validated_data.get('status', None)  # Default to None if not provided
        
        # Get distributor_id and franchise_id from request data
        distributor_id = self.request.data.get('distributor_id')
        franchise_id = self.request.data.get('franchise_id')

        if user.role == 'SuperAdmin':
            if distributor_id:
                try:
                    distributor = Distributor.objects.get(id=distributor_id)
                    existing_inventory = Inventory.objects.filter(
                        distributor=distributor,
                        product=product
                    ).first()
                    
                    if existing_inventory:
                        InventoryChangeLog.objects.create(
                            inventory=existing_inventory,
                            user=user,
                            old_quantity=existing_inventory.quantity,
                            new_quantity=existing_inventory.quantity + quantity,
                            action='update'
                        )
                        existing_inventory.quantity += quantity
                        if status is not None:  # Only update status if provided
                            existing_inventory.status = status
                        existing_inventory.save()
                        return existing_inventory
                    else:
                        # For new inventory, only include status if provided
                        create_kwargs = {'distributor': distributor}
                        if status is not None:
                            create_kwargs['status'] = status
                        inventory = serializer.save(**create_kwargs)
                        InventoryChangeLog.objects.create(
                            inventory=inventory,
                            user=user,
                            old_quantity=0,
                            new_quantity=quantity,
                            action='add'
                        )
                        return inventory
                except Distributor.DoesNotExist:
                    raise serializers.ValidationError("Distributor not found")
                    
            elif franchise_id:
                try:
                    franchise = Franchise.objects.get(id=franchise_id)
                    existing_inventory = Inventory.objects.filter(
                        franchise=franchise,
                        product=product
                    ).first()
                    
                    if existing_inventory:
                        InventoryChangeLog.objects.create(
                            inventory=existing_inventory,
                            user=user,
                            old_quantity=existing_inventory.quantity,
                            new_quantity=existing_inventory.quantity + quantity,
                            action='update'
                        )
                        existing_inventory.quantity += quantity
                        if status is not None:  # Only update status if provided
                            existing_inventory.status = status
                        existing_inventory.save()
                        return existing_inventory
                    else:
                        create_kwargs = {'franchise': franchise}
                        if status is not None:
                            create_kwargs['status'] = status
                        inventory = serializer.save(**create_kwargs)
                        InventoryChangeLog.objects.create(
                            inventory=inventory,
                            user=user,
                            old_quantity=0,
                            new_quantity=quantity,
                            action='add'
                        )
                        return inventory
                except Franchise.DoesNotExist:
                    raise serializers.ValidationError("Franchise not found")
            else:
                existing_inventory = Inventory.objects.filter(
                    factory=user.factory,
                    product=product
                ).first()

                if existing_inventory:
                    InventoryChangeLog.objects.create(
                        inventory=existing_inventory,
                        user=user,
                        old_quantity=existing_inventory.quantity,
                        new_quantity=existing_inventory.quantity + quantity,
                        action='update'
                    )
                    existing_inventory.quantity += quantity
                    if status is not None:  # Only update status if provided
                        existing_inventory.status = status
                    existing_inventory.save()
                    return existing_inventory
                else:
                    create_kwargs = {'factory': user.factory}
                    if status is not None:
                        create_kwargs['status'] = status
                    inventory = serializer.save(**create_kwargs)
                    InventoryChangeLog.objects.create(
                        inventory=inventory,
                        user=user,
                        old_quantity=0,
                        new_quantity=quantity,
                        action='add'
                    )
                    return inventory

        elif user.role == 'Distributor':
            if franchise_id:
                try:
                    franchise = Franchise.objects.get(
                        id=franchise_id, 
                        distributor=user.distributor
                    )
                    existing_inventory = Inventory.objects.filter(
                        franchise=franchise,
                        product=product
                    ).first()
                    
                    if existing_inventory:
                        InventoryChangeLog.objects.create(
                            inventory=existing_inventory,
                            user=user,
                            old_quantity=existing_inventory.quantity,
                            new_quantity=existing_inventory.quantity + quantity,
                            action='update'
                        )
                        existing_inventory.quantity += quantity
                        if status is not None:  # Only update status if provided
                            existing_inventory.status = status
                        existing_inventory.save()
                        return existing_inventory
                    else:
                        create_kwargs = {'franchise': franchise}
                        if status is not None:
                            create_kwargs['status'] = status
                        inventory = serializer.save(**create_kwargs)
                        InventoryChangeLog.objects.create(
                            inventory=inventory,
                            user=user,
                            old_quantity=0,
                            new_quantity=quantity,
                            action='add'
                        )
                        return inventory
                except Franchise.DoesNotExist:
                    raise serializers.ValidationError("Franchise not found or does not belong to your distributorship")
            else:
                existing_inventory = Inventory.objects.filter(
                    distributor=user.distributor,
                    product=product
                ).first()

                if existing_inventory:
                    InventoryChangeLog.objects.create(
                        inventory=existing_inventory,
                        user=user,
                        old_quantity=existing_inventory.quantity,
                        new_quantity=existing_inventory.quantity + quantity,
                        action='update'
                    )
                    existing_inventory.quantity += quantity
                    if status is not None:  # Only update status if provided
                        existing_inventory.status = status
                    existing_inventory.save()
                    return existing_inventory
                else:
                    create_kwargs = {'distributor': user.distributor}
                    if status is not None:
                        create_kwargs['status'] = status
                    inventory = serializer.save(**create_kwargs)
                    InventoryChangeLog.objects.create(
                        inventory=inventory,
                        user=user,
                        old_quantity=0,
                        new_quantity=quantity,
                        action='add'
                    )
                    return inventory

        elif user.role == 'Franchise':
            existing_inventory = Inventory.objects.filter(
                franchise=user.franchise,
                product=product
            ).first()

            if existing_inventory:
                InventoryChangeLog.objects.create(
                    inventory=existing_inventory,
                    user=user,
                    old_quantity=existing_inventory.quantity,
                    new_quantity=existing_inventory.quantity + quantity,
                    action='update'
                )
                existing_inventory.quantity += quantity
                if status is not None:  # Only update status if provided
                    existing_inventory.status = status
                existing_inventory.save()
                return existing_inventory
            else:
                create_kwargs = {'franchise': user.franchise}
                if status is not None:
                    create_kwargs['status'] = status
                inventory = serializer.save(**create_kwargs)
                InventoryChangeLog.objects.create(
                    inventory=inventory,
                    user=user,
                    old_quantity=0,
                    new_quantity=quantity,
                    action='add'
                )
                return inventory

        else:
            raise serializers.ValidationError("User does not have permission to create inventory")

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
                            'id': inventory.id,
                            'product_id': inventory.product.id,
                            'product': inventory.product.name,
                            'quantity': inventory.quantity,
                            'status': inventory.status
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
            inventory_summary = {}  # Changed from list to dictionary
            for distributor in distributors:
                distributor_inventory = {
                    'inventory': [
                        {
                            'id': inventory.id,
                            'product_id': inventory.product.id, 
                            'product': inventory.product.name,
                            'quantity': inventory.quantity,
                            'status': inventory.status
                        } for inventory in distributor.inventory.all()
                    ],
                    'franchises': {}
                }
                franchises = Franchise.objects.filter(distributor=distributor)
                for franchise in franchises:
                    distributor_inventory['franchises'][franchise.name] = [  # Accessing the correct dictionary
                        {
                            'id': inventory.id,
                            'product_id': inventory.product.id,
                            'product': inventory.product.name,
                            'quantity': inventory.quantity,
                            'status': inventory.status
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
                            'id': inventory.id,
                            'product_id': inventory.product.id,
                            'product': inventory.product.name,
                            'quantity': inventory.quantity,
                            'status': inventory.status
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
                        'id': inventory.id,
                        'product_id': inventory.product.id,
                        'product': inventory.product.name,
                        'quantity': inventory.quantity,
                        'status': inventory.status
                    } for inventory in franchise.inventory.all()
                ]
            return Response(inventory_summary)
        elif user.role == 'Franchise':  # Added handling for Franchise role
            # Get the franchise's inventory
            inventory_summary = {
                user.franchise.name: {
                    'inventory': [
                        {
                            'id': inventory.id,
                            'product_id': inventory.product.id,
                            'product': inventory.product.name,
                            'quantity': inventory.quantity,
                            'status': inventory.status
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
    permission_classes = [IsAuthenticated]
    filterset_class = OrderFilter
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter,rest_filters.OrderingFilter]  # Added SearchFilter
    search_fields = ['phone_number', 'sales_person__username','delivery_address','full_name']  # Specify the fields to search
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

        
        # Validate inventory before creating order
        order_products_data = self.request.data.get('order_products', [])
        for order_product_data in order_products_data:
            product_id = order_product_data['product_id']
            quantity = order_product_data['quantity']

            try:
                # Find inventory item using product_id and franchise
                if salesperson.role == 'Franchise' or salesperson.role == 'SalesPerson':
                    franchise = salesperson.franchise
                    inventory_item = Inventory.objects.get(
                        product_id=product_id,
                        franchise=franchise  # Ensure the inventory belongs to the franchise
                    )
                elif salesperson.role == 'Distributor':
                    distributor = salesperson.distributor
                    inventory_item = Inventory.objects.get(
                        product_id=product_id,
                        distributor=distributor
                    )
                elif salesperson.role == 'SuperAdmin':
                    factory=salesperson.factory
                    inventory_item = Inventory.objects.get(
                        product_id=product_id,
                        factory=factory
                    )
                if inventory_item.quantity < quantity:
                    raise serializers.ValidationError(
                        f"Insufficient inventory for product {inventory_item.product.name}. "
                        f"Available: {inventory_item.quantity}, Requested: {quantity}"
                    )
            except Inventory.DoesNotExist:
                raise serializers.ValidationError(
                    f"Product with ID {product_id} not found in franchise inventory"
                )

        # Create order if validation passes
        if salesperson.role == 'Franchise' or salesperson.role == 'SalesPerson':
            franchise = salesperson.franchise
            order = serializer.save(sales_person=salesperson, franchise=franchise)
        elif salesperson.role == 'Distributor':
            distributor = salesperson.distributor
            order = serializer.save(distributor=distributor, sales_person=salesperson)
        elif salesperson.role == 'SuperAdmin':
            factory=salesperson.factory
            order = serializer.save(factory=factory, sales_person=salesperson)

        # Update inventory quantities and create logs
        for order_product_data in order_products_data:
            product_id = order_product_data['product_id']
            quantity = order_product_data['quantity']

            if salesperson.role == 'Franchise' or salesperson.role == 'SalesPerson':
                    franchise = salesperson.franchise
                    inventory_item = Inventory.objects.get(
                        product_id=product_id,
                        franchise=franchise  # Ensure the inventory belongs to the franchise
                    )
            elif salesperson.role == 'Distributor':
                    distributor = salesperson.distributor
                    inventory_item = Inventory.objects.get(
                        product_id=product_id,
                        distributor=distributor
                    )
            elif salesperson.role == 'SuperAdmin':
                    factory=salesperson.factory
                    inventory_item = Inventory.objects.get(
                        product_id=product_id,
                        factory=factory
                    )
            if inventory_item.quantity < quantity:
                    raise serializers.ValidationError(
                        f"Insufficient inventory for product {inventory_item.product.name}. "
                        f"Available: {inventory_item.quantity}, Requested: {quantity}"
                    )
            old_quantity = inventory_item.quantity
            inventory_item.quantity -= quantity
            inventory_item.save()

            # Create log for inventory update from order
            InventoryChangeLog.objects.create(
                inventory=inventory_item,
                user=self.request.user,
                old_quantity=old_quantity,
                new_quantity=inventory_item.quantity,
                action='order_created'
            )

        return order

class OrderUpdateView(generics.UpdateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def update(self, request, *args, **kwargs):
        order = self.get_object()
        previous_status = order.order_status  
        
        response = super().update(request, *args, **kwargs)
        order.refresh_from_db()

        # Handle order cancellation
        if order.order_status == "Cancelled" and previous_status != "Cancelled":
            # Restore inventory quantities for each product in the order
            order_products = OrderProduct.objects.filter(order=order)
            for order_product in order_products:
                try:
                    inventory = Inventory.objects.get(
                        product=order_product.product,
                        franchise=order.franchise
                    )
                    old_quantity = inventory.quantity
                    inventory.quantity += order_product.quantity
                    inventory.save()

                    # Log the inventory change
                    InventoryChangeLog.objects.create(
                        inventory=inventory,
                        user=request.user,
                        old_quantity=old_quantity,
                        new_quantity=inventory.quantity,
                        action='order_cancelled'
                    )
                except Inventory.DoesNotExist:
                    return Response(
                        {"detail": f"Inventory not found for product {order_product.product.name}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

        if order.order_status == "Delivered" and previous_status != "Delivered":
            try:
                distributor_commission = Commission.objects.get(
                    distributor=order.distributor,
                    sales_person=order.sales_person
                )
                
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
            # Get products and their inventory IDs from factory's inventory
            factory_inventory = Inventory.objects.filter(factory=user.factory).values(
                'id', 
                'product', 
                'product__name',
                'quantity',
                'status'
            )
            product_list = []
            for inv in factory_inventory:
                product_list.append({
                    'inventory_id': inv['id'],
                    'product_id': inv['product'],
                    'product_name': inv['product__name'],
                    'quantity': inv['quantity'],
                    'status': inv['status']
                })
            return product_list
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
        user = self.request.user
        
        # Retrieve the new quantity from the request data
        new_quantity = self.request.data.get('new_quantity')        
        # Create a log entry before updating
        InventoryChangeLog.objects.create(
            inventory=inventory_item,
            user=user,
            old_quantity=inventory_item.quantity,
            new_quantity=new_quantity if new_quantity is not None else inventory_item.quantity,
            action='update'
        )
        
        # Update the inventory item's quantity if new_quantity is provided
        if new_quantity is not None:
            inventory_item.quantity = new_quantity
        
        # Save the updated inventory item using the serializer
        serializer.save(quantity=inventory_item.quantity)

    def perform_destroy(self, instance):
        user = self.request.user
        
        # Create a log entry before deleting
        InventoryChangeLog.objects.create(
            inventory=instance,
            user=user,
            old_quantity=instance.quantity,
            new_quantity=0,
            action='deleted'
        )
        
        # Perform the deletion
        instance.delete()


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
    queryset = InventoryChangeLog.objects.all().order_by('-id')

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

class AllProductsListView(generics.ListCreateAPIView):
    serializer_class = ProductSerializer
    queryset = Product.objects.all()
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name', 'id']
    pagination_class = CustomPagination

    def perform_create(self, serializer):
        user = self.request.user
        if user.role != 'SuperAdmin':
            raise serializers.ValidationError("Only SuperAdmin can create products")
        serializer.save()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if isinstance(queryset, list):  # If it's our custom product list
            return Response(queryset)
        # Otherwise, use default serializer behavior
        return super().list(request, *args, **kwargs)

class SalesStatisticsView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = self.request.user
        today = timezone.now().date()
        
        if user.role == 'SuperAdmin':
            # Get daily statistics
            daily_stats = Order.objects.filter(
                date=today
            ).aggregate(
                total_orders=Count('id'),
                total_sales=Sum('total_amount')
            )
            
            # Get all-time statistics
            all_time_stats = Order.objects.all().aggregate(
                total_orders=Count('id'),
                total_sales=Sum('total_amount')
            )
            
            return Response({
                'date': today,
                'total_orders': daily_stats['total_orders'] or 0,
                'total_sales': daily_stats['total_sales'] or 0,
                'all_time_orders': all_time_stats['total_orders'] or 0,
                'all_time_sales': all_time_stats['total_sales'] or 0
            })
            
        elif user.role == 'Distributor':
            # Get franchises under this distributor
            franchises = Franchise.objects.filter(distributor=user.distributor)
            
            # Get daily statistics
            daily_stats = Order.objects.filter(
                date=today,
                franchise__in=franchises
            ).aggregate(
                total_orders=Count('id'),
                total_sales=Sum('total_amount')
            )
            
            # Get all-time statistics
            all_time_stats = Order.objects.filter(
                franchise__in=franchises
            ).aggregate(
                total_orders=Count('id'),
                total_sales=Sum('total_amount')
            )
            
            return Response({
                'date': today,
                'total_orders': daily_stats['total_orders'] or 0,
                'total_sales': daily_stats['total_sales'] or 0,
                'all_time_orders': all_time_stats['total_orders'] or 0,
                'all_time_sales': all_time_stats['total_sales'] or 0
            })
            
        elif user.role == 'Franchise':
            # Get daily statistics
            daily_stats = Order.objects.filter(
                date=today,
                franchise=user.franchise
            ).aggregate(
                total_orders=Count('id'),
                total_sales=Sum('total_amount')
            )
            
            # Get all-time statistics
            all_time_stats = Order.objects.filter(
                franchise=user.franchise
            ).aggregate(
                total_orders=Count('id'),
                total_sales=Sum('total_amount')
            )
            
            return Response({
                'date': today,
                'total_orders': daily_stats['total_orders'] or 0,
                'total_sales': daily_stats['total_sales'] or 0,
                'all_time_orders': all_time_stats['total_orders'] or 0,
                'all_time_sales': all_time_stats['total_sales'] or 0
            })
            
        elif user.role == 'SalesPerson':
            # Get daily statistics
            daily_stats = Order.objects.filter(
                date=today,
                sales_person=user
            ).aggregate(
                total_orders=Count('id'),
                total_sales=Sum('total_amount')
            )
            
            # Get all-time statistics
            all_time_stats = Order.objects.filter(
                sales_person=user
            ).aggregate(
                total_orders=Count('id'),
                total_sales=Sum('total_amount')
            )
            
            return Response({
                'date': today,
                'total_orders': daily_stats['total_orders'] or 0,
                'total_sales': daily_stats['total_sales'] or 0,
                'all_time_orders': all_time_stats['total_orders'] or 0,
                'all_time_sales': all_time_stats['total_sales'] or 0,
            })
            
        return Response({
            "detail": "You don't have permission to view statistics"
        }, status=status.HTTP_403_FORBIDDEN)
    

class LatestOrdersView(generics.ListAPIView):
    queryset = Order.objects.order_by('-id')[:5]  # Get the latest 5 orders
    serializer_class = OrderSerializer

class UserInventoryLogs(generics.ListAPIView):
    serializer_class = InventoryChangeLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        
        if user.role == 'SuperAdmin':
            # Get logs for factory inventory
            return InventoryChangeLog.objects.filter(
                inventory__factory=user.factory
            ).order_by('-id')
            
        elif user.role == 'Distributor':
            # Get logs for distributor inventory
            return InventoryChangeLog.objects.filter(
                inventory__distributor=user.distributor
            ).order_by('-id')
            
        elif user.role == 'Franchise':
            # Get logs for franchise inventory
            return InventoryChangeLog.objects.filter(
                inventory__franchise=user.franchise
            ).order_by('-id')
            
        elif user.role == 'SalesPerson':
            # Get logs where the user is the one who made the change
            return InventoryChangeLog.objects.filter(
                user=user
            ).order_by('-id')
            
        return InventoryChangeLog.objects.none()  # Return empty queryset for unknown roles
    

class TopSalespersonView(generics.ListAPIView):
    serializer_class = TopSalespersonSerializer

    def get_queryset(self):
        # Get all users with role 'SalesPerson'
        salespersons = CustomUser.objects.filter(role='SalesPerson')
        
        # Annotate each salesperson with their total sales count and amount
        salespersons = salespersons.annotate(
            sales_count=Count('orders', filter=models.Q(orders__order_status='Delivered')),
            total_sales=Sum('orders__total_amount', filter=models.Q(orders__order_status='Delivered'))
        ).order_by('-sales_count', '-total_sales')[:5]  # Get top 5 by sales count, then by amount
        
        # Replace None values with 0
        for salesperson in salespersons:
            if salesperson.total_sales is None:
                salesperson.total_sales = 0.0
            if salesperson.sales_count is None:
                salesperson.sales_count = 0
        
        return salespersons

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        # Add sales count and total sales to each salesperson's data
        data = serializer.data
        for index, item in enumerate(data):
            item['sales_count'] = queryset[index].sales_count
            item['total_sales'] = float(queryset[index].total_sales or 0)
        
        return Response(data)

class RevenueView(generics.ListAPIView):

    def get(self, request, *args, **kwargs):
        filter_type = request.GET.get('filter', 'monthly')  # Default to monthly
        today = timezone.now().date()

        try:
            if filter_type == 'weekly':
                revenue = (
                    Order.objects.filter(created_at__year=today.year)
                    .annotate(period=TruncWeek('created_at'))
                    .values('period')
                    .annotate(
                        total_revenue=Sum('total_amount', default=0),
                        order_count=Count('id')
                    )
                    .order_by('period')
                )
                
            elif filter_type == 'yearly':
                revenue = (
                    Order.objects.annotate(period=TruncYear('created_at'))
                    .values('period')
                    .annotate(
                        total_revenue=Sum('total_amount', default=0),
                        order_count=Count('id')
                    )
                    .order_by('period')
                )
                
            else:  # Default is monthly
                revenue = (
                    Order.objects.annotate(period=TruncMonth('created_at'))
                    .values('period')
                    .annotate(
                        total_revenue=Sum('total_amount', default=0),
                        order_count=Count('id')
                    )
                    .order_by('period')
                )

            # Format the response data
            response_data = [{
                'period': entry['period'].strftime(
                    '%Y-%m-%d' if filter_type == 'weekly' 
                    else '%Y-%m' if filter_type == 'monthly'
                    else '%Y'
                ),
                'total_revenue': float(entry['total_revenue']),
                'order_count': entry['order_count']
            } for entry in revenue]

            return Response({
                'filter_type': filter_type,
                'data': response_data
            })

        except Exception as e:
            return Response(
                {'error': f'Failed to fetch revenue data: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

class TopProductsView(generics.ListAPIView):
    def get(self, request, *args, **kwargs):
        try:
            # Get all order products and aggregate their quantities and amounts
            top_products = (
                OrderProduct.objects.filter(
                    order__order_status='Delivered'  # Only count delivered orders
                ).values(
                    'product__product__id',  # Get the actual product ID
                    'product__product__name'  # Get the product name
                ).annotate(
                    total_quantity=Sum('quantity'),
                    total_amount=Sum(
                        models.F('quantity') * models.F('order__total_amount') / 
                        models.Subquery(
                            OrderProduct.objects.filter(order=models.OuterRef('order'))
                            .values('order')
                            .annotate(total_qty=Sum('quantity'))
                            .values('total_qty')
                        )
                    )
                ).order_by('-total_quantity')[:5]  # Get top 5 by quantity
            )

            # Format the response data
            response_data = [{
                'product_id': item['product__product__id'],
                'product_name': item['product__product__name'],
                'total_quantity': item['total_quantity'],
                'total_amount': round(float(item['total_amount']), 2) if item['total_amount'] else 0.0
            } for item in top_products]

            return Response({
                'count': len(response_data),
                'data': response_data
            })

        except Exception as e:
            return Response(
                {'error': f'Failed to fetch top products data: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
