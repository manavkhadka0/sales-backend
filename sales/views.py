from django.forms import DecimalField
from django.shortcuts import render
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import Inventory, Order,Commission,Product,InventoryChangeLog,InventoryRequest, OrderProduct
from account.models import CustomUser, Distributor, Franchise,Factory
from .serializers import InventorySerializer, OrderSerializer,ProductSerializer,InventoryChangeLogSerializer,InventoryRequestSerializer, RawMaterialSerializer, TopSalespersonSerializer
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

    def _format_inventory_data(self, inventory_queryset):
        """Helper method to format inventory data consistently"""
        return [
            {
                'id': inventory.id,
                'product_id': inventory.product.id,
                'product': inventory.product.name,
                'quantity': inventory.quantity,
                'status': inventory.status
            } for inventory in inventory_queryset.filter(status='ready_to_dispatch')
        ]

    def _get_franchise_data(self, franchise):
        """Helper method to get franchise inventory data"""
        return {
            'id': franchise.id,
            'inventory': self._format_inventory_data(franchise.inventory.all())
        }

    def _get_distributor_data(self, distributor):
        """Helper method to get distributor and its franchises inventory data"""
        distributor_data = {
            'id': distributor.id,
            'inventory': self._format_inventory_data(distributor.inventory.all()),
            'franchises': {}
        }
        
        franchises = Franchise.objects.filter(distributor=distributor)
        for franchise in franchises:
            distributor_data['franchises'][franchise.name] = self._get_franchise_data(franchise)
            
        return distributor_data

    def list(self, request, *args, **kwargs):
        user = self.request.user
        
        if user.role == 'SuperAdmin':
            factories = Factory.objects.prefetch_related('inventory')
            inventory_summary = {}
            
            for factory in factories:
                factory_data = {
                    'id': factory.id,
                    'inventory': self._format_inventory_data(factory.inventory.all()),
                    'distributors': {}
                }
                
                distributors = Distributor.objects.prefetch_related('inventory')
                for distributor in distributors:
                    factory_data['distributors'][distributor.name] = self._get_distributor_data(distributor)
                
                inventory_summary[factory.name] = factory_data
            
            return Response(inventory_summary)
            
        elif user.role == 'Distributor':
            inventory_summary = {
                user.distributor.name: self._get_distributor_data(user.distributor)
            }
            return Response(inventory_summary)
            
        elif user.role in ['Franchise', 'SalesPerson']:
            inventory_summary = {
                user.franchise.name: self._get_franchise_data(user.franchise)
            }
            return Response(inventory_summary)
            
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        user = self.request.user
        product = serializer.validated_data['product']
        quantity = serializer.validated_data['quantity']
        status = serializer.validated_data.get('status', None)

        def get_inventory_owner():
            """Helper method to determine inventory owner based on user role and request data"""
            distributor_id = self.request.data.get('distributor_id')
            franchise_id = self.request.data.get('franchise_id')

            if user.role == 'SuperAdmin':
                if distributor_id:
                    try:
                        return Distributor.objects.get(id=distributor_id), 'distributor'
                    except Distributor.DoesNotExist:
                        raise serializers.ValidationError("Distributor not found")
                elif franchise_id:
                    try:
                        return Franchise.objects.get(id=franchise_id), 'franchise'
                    except Franchise.DoesNotExist:
                        raise serializers.ValidationError("Franchise not found")
                return user.factory, 'factory'
            
            elif user.role == 'Distributor':
                if franchise_id:
                    try:
                        franchise = Franchise.objects.get(id=franchise_id, distributor=user.distributor)
                        return franchise, 'franchise'
                    except Franchise.DoesNotExist:
                        raise serializers.ValidationError("Franchise not found or does not belong to your distributorship")
                return user.distributor, 'distributor'
            
            elif user.role == 'Franchise':
                return user.franchise, 'franchise'
            
            raise serializers.ValidationError("User does not have permission to create inventory")

        def update_or_create_inventory(owner, owner_type):
            """Helper method to handle inventory update or creation"""
            filter_kwargs = {f"{owner_type}": owner, 'product': product}
            existing_inventory = Inventory.objects.filter(**filter_kwargs).first()

            if existing_inventory:
                # Update existing inventory
                new_quantity = existing_inventory.quantity + quantity
                InventoryChangeLog.objects.create(
                    inventory=existing_inventory,
                    user=user,
                    old_quantity=existing_inventory.quantity,
                    new_quantity=new_quantity,
                    action='update'
                )
                existing_inventory.quantity = new_quantity
                if status is not None:
                    existing_inventory.status = status
                existing_inventory.save()
                return existing_inventory
            else:
                # Create new inventory
                create_kwargs = {owner_type: owner}
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

        # Get inventory owner and type, then update or create inventory
        owner, owner_type = get_inventory_owner()
        return update_or_create_inventory(owner, owner_type)

class FactoryInventoryListView(generics.ListAPIView):
    serializer_class = InventorySerializer
    queryset = Inventory.objects.filter(status='ready_to_dispatch')

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

    def _format_inventory_data(self, inventory_queryset):
        """Helper method to format inventory data consistently"""
        return [
            {
                'id': inventory.id,
                'product_id': inventory.product.id,
                'product': inventory.product.name,
                'quantity': inventory.quantity,
                'status': inventory.status
            } for inventory in inventory_queryset
        ]

    def _get_distributor_data(self, distributor):
        """Helper method to get distributor inventory data"""
        return {
            'inventory': self._format_inventory_data(distributor.inventory.all())
        }

    def list(self, request, *args, **kwargs):
        user = self.request.user
        
        if user.role == 'SuperAdmin':
            distributors = Distributor.objects.prefetch_related('inventory')
            inventory_summary = {
                distributor.name: self._get_distributor_data(distributor)
                for distributor in distributors
            }
            return Response(inventory_summary)
            
        elif user.role == 'Distributor':
            inventory_summary = {
                user.distributor.name: self._get_distributor_data(user.distributor)
            }
            return Response(inventory_summary)
            
        elif user.role == 'Franchise':
            inventory_summary = {
                user.franchise.name: {
                    'inventory': self._format_inventory_data(user.franchise.inventory.all())
                }
            }
            return Response(inventory_summary)
            
        return Response([])  # Return an empty Response for non-authorized users

class FranchiseInventoryListView(generics.ListAPIView):
    serializer_class = InventorySerializer
    queryset = Inventory.objects.all()

    def _format_inventory_data(self, inventory_queryset):
        """Helper method to format inventory data consistently"""
        return [
            {
                'id': inventory.id,
                'product_id': inventory.product.id,
                'product': inventory.product.name,
                'quantity': inventory.quantity,
            } for inventory in inventory_queryset.filter(status='ready_to_dispatch')
        ]

    def list(self, request, *args, **kwargs):
        user = self.request.user

        if user.role == 'SuperAdmin':
            # Get all franchises with their distributors
            franchises = Franchise.objects.prefetch_related('inventory', 'distributor').all()
            inventory_summary = {}
            
            for franchise in franchises:
                inventory_summary[franchise.name] = {
                    'distributor_name': franchise.distributor.name if franchise.distributor else "No Distributor",
                    'inventory': self._format_inventory_data(franchise.inventory.all())
                }
            
            return Response(inventory_summary)

        elif user.role == 'Distributor':
            # Get franchises under this distributor
            franchises = Franchise.objects.filter(distributor=user.distributor).prefetch_related('inventory')
            inventory_summary = {}
            
            for franchise in franchises:
                inventory_summary[franchise.name] = {
                    'distributor_name': user.distributor.name,
                    'inventory': self._format_inventory_data(franchise.inventory.all())
                }
            
            return Response(inventory_summary)

        elif user.role == 'Franchise':
            # Get only this franchise's inventory
            inventory_summary = {
                user.franchise.name: {
                    'distributor_name': user.franchise.distributor.name if user.franchise.distributor else "No Distributor",
                    'inventory': self._format_inventory_data(user.franchise.inventory.all())
                }
            }
            return Response(inventory_summary)

        return Response({})  # Return empty dict for unauthorized users

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
        phone_number = self.request.data.get('phone_number')
        
        # Get the order products data
        order_products_data = self.request.data.get('order_products', [])
        
        # Check for recent orders with same phone number and products
        seven_days_ago = timezone.now() - timezone.timedelta(days=7)
        
        for order_product_data in order_products_data:
            product_id = order_product_data['product_id']
            product = Product.objects.get(id=product_id)
            # Check if this phone number has ordered this product in the last 7 days
            recent_orders = Order.objects.filter(
                phone_number=phone_number,
                created_at__gte=seven_days_ago
            ).prefetch_related('order_products')
            
            for order in recent_orders:
                if order.order_products.filter(product__product_id=product_id).exists():
                    raise serializers.ValidationError(
                        f"This phone number has already ordered {product.name} within the last 7 days. "
                        "Please wait before ordering the same product again."
                    )
        
        # Validate inventory before creating order
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
            order_products = OrderProduct.objects.filter(order=order).select_related('product__product')
            for order_product in order_products:
                try:
                    # Get inventory using the product instance from order_product
                    inventory = Inventory.objects.get(
                        product__id=order_product.product.product.id,  # Use the product ID
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
                        {"detail": f"Inventory not found for product {order_product.product.product.name}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        
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

    def _format_inventory_data(self, inventory_queryset, include_status=False):
        """Helper method to format inventory data consistently"""
        base_fields = {
            'id', 
            'product', 
            'product__name',
            'quantity'
        }
        
        if include_status:
            base_fields.add('status')
            
        inventory_data = inventory_queryset.filter(status='ready_to_dispatch').values(*base_fields)
        
        product_list = []
        for inv in inventory_data:
            product_dict = {
                'inventory_id': inv['id'],
                'product_id': inv['product'],
                'product_name': inv['product__name'],
                'quantity': inv['quantity']
            }
            if include_status:
                product_dict['status'] = inv['status']
            product_list.append(product_dict)
            
        return product_list

    def get_queryset(self):
        user = self.request.user
        
        if user.role in ['Franchise', 'SalesPerson']:
            return self._format_inventory_data(
                Inventory.objects.filter(franchise=user.franchise)
            )
            
        elif user.role == 'Distributor':
            return self._format_inventory_data(
                Inventory.objects.filter(distributor=user.distributor)
            )
            
        elif user.role == 'SuperAdmin':
            return self._format_inventory_data(
                Inventory.objects.filter(factory=user.factory),
                include_status=True
            )
            
        return Product.objects.none()  # Return empty queryset for other roles

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if isinstance(queryset, list):  # If it's our custom product list
            return Response(queryset)
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

    def get_stats_for_queryset(self, queryset, today):
        """Helper method to get statistics for a queryset"""
        daily_stats = queryset.filter(date=today).aggregate(
            total_orders=Count('id'),
            total_sales=Sum('total_amount')
        )
        
        all_time_stats = queryset.aggregate(
            total_orders=Count('id'),
            total_sales=Sum('total_amount')
        )
        
        return {
            'date': today,
            'total_orders': daily_stats['total_orders'] or 0,
            'total_sales': daily_stats['total_sales'] or 0,
            'all_time_orders': all_time_stats['total_orders'] or 0,
            'all_time_sales': all_time_stats['total_sales'] or 0
        }

    def get(self, request):
        user = self.request.user
        today = timezone.now().date()
        
        if user.role == 'SuperAdmin':
            queryset = Order.objects.all()
        elif user.role == 'Distributor':
            franchises = Franchise.objects.filter(distributor=user.distributor)
            queryset = Order.objects.filter(franchise__in=franchises)
        elif user.role == 'Franchise':
            queryset = Order.objects.filter(franchise=user.franchise)
        elif user.role == 'SalesPerson':
            queryset = Order.objects.filter(sales_person=user)
        else:
            return Response(
                {"detail": "You don't have permission to view statistics"},
                status=status.HTTP_403_FORBIDDEN
            )
            
        return Response(self.get_stats_for_queryset(queryset, today))
    

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
        # Get all users with role 'SalesPerson' and annotate with sales data
        salespersons = CustomUser.objects.filter(role='SalesPerson')
        
        # Annotate and filter out those with no sales
        salespersons = salespersons.annotate(
            sales_count=Count('orders'),
            total_sales=Sum('orders__total_amount')
        ).filter(
            sales_count__gt=0,  # Only include those with sales count greater than 0
            total_sales__gt=0   # Only include those with total sales greater than 0
        ).order_by('-sales_count', '-total_sales')[:5]  # Get top 5 by sales count, then by amount
        
        return salespersons

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        data = serializer.data
        for index, item in enumerate(data):
            item['sales_count'] = queryset[index].sales_count
            item['total_sales'] = float(queryset[index].total_sales)
        
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

class RawMaterialListView(generics.ListAPIView):
    serializer_class = RawMaterialSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        
        # Only SuperAdmin can access raw materials
        if user.role == 'SuperAdmin':
            return Inventory.objects.filter(
                factory=user.factory,
                status='raw_material'
            )
        
        # Return empty queryset for all other roles
        return Inventory.objects.none()

    def list(self, request, *args, **kwargs):
        if request.user.role != 'SuperAdmin':
            return Response(
                {"detail": "Only SuperAdmin can access raw materials."},
                status=status.HTTP_403_FORBIDDEN
            )
            
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            'count': queryset.count(),
            'results': serializer.data
        })


