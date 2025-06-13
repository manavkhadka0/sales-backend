from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import Inventory, Order, Commission, Product, InventoryChangeLog, InventoryRequest, OrderProduct, PromoCode, Location
from account.models import CustomUser, Distributor, Franchise, Factory
from .serializers import InventorySerializer, OrderSerializer, ProductSerializer, InventoryChangeLogSerializer, InventoryRequestSerializer, RawMaterialSerializer, TopSalespersonSerializer, PromoCodeSerializer, SalesPersonStatisticsSerializer, LocationSerializer, FileUploadSerializer
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from django_filters import rest_framework as django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters as rest_filters
from rest_framework.pagination import PageNumberPagination
from rest_framework import serializers
from django.utils import timezone
from django.db.models import Count, Sum, Q
from django.db import models
from django.db.models.functions import TruncMonth, TruncWeek, TruncYear
from django.http import HttpResponse
import csv
import openpyxl
import io
from datetime import datetime
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db import transaction


# Create your views here.

class InventoryListCreateView(generics.ListCreateAPIView):
    serializer_class = InventorySerializer
    permission_classes = [IsAuthenticated]

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
            distributor_data['franchises'][franchise.name] = self._get_franchise_data(
                franchise)

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

                distributors = Distributor.objects.prefetch_related(
                    'inventory')
                for distributor in distributors:
                    factory_data['distributors'][distributor.name] = self._get_distributor_data(
                        distributor)

                inventory_summary[factory.name] = factory_data

            return Response(inventory_summary)

        elif user.role == 'Distributor':
            inventory_summary = {
                user.distributor.name: self._get_distributor_data(
                    user.distributor)
            }
            return Response(inventory_summary)

        elif user.role in ['Franchise', 'Packaging']:
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
            """Helper method to determine inventory owner based on user role"""
            if user.role == 'SuperAdmin':
                # SuperAdmin can only add inventory to their own factory
                return user.factory, 'factory'

            elif user.role == 'Distributor':
                # Distributor can only add inventory to their own distributor account
                return user.distributor, 'distributor'

            elif user.role in ['Franchise', 'Packaging']:
                # Franchise and Packaging can only add inventory to their own franchise
                return user.franchise, 'franchise'

            raise serializers.ValidationError(
                "User does not have permission to create inventory")

        def update_or_create_inventory(owner, owner_type):
            """Helper method to handle inventory update or creation"""
            filter_kwargs = {f"{owner_type}": owner, 'product': product}
            existing_inventory = Inventory.objects.filter(
                **filter_kwargs).first()

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
            # Return the summary for SuperAdmin
            return Response(inventory_summary)

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
            distributors = Distributor.objects.filter(
                factory=user.factory).prefetch_related('inventory')
            inventory_summary = {
                distributor.name: self._get_distributor_data(distributor)
                for distributor in distributors
            }
            return Response(inventory_summary)

        elif user.role == 'Distributor':
            inventory_summary = {
                user.distributor.name: self._get_distributor_data(
                    user.distributor)
            }
            return Response(inventory_summary)

        elif user.role in ['Franchise', 'Packaging']:
            inventory_summary = {
                user.franchise.name: {
                    'inventory': self._format_inventory_data(user.franchise.inventory.all())
                }
            }
            return Response(inventory_summary)

        # Return an empty Response for non-authorized users
        return Response([])


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
            franchises = Franchise.objects.filter(
                distributor__factory=user.factory).prefetch_related(
                'inventory', 'distributor').all()
            inventory_summary = {}

            for franchise in franchises:
                inventory_summary[franchise.name] = {
                    'distributor_name': franchise.distributor.name if franchise.distributor else "No Distributor",
                    'inventory': self._format_inventory_data(franchise.inventory.all())
                }

            return Response(inventory_summary)

        elif user.role == 'Distributor':
            # Get franchises under this distributor
            franchises = Franchise.objects.filter(
                distributor=user.distributor).prefetch_related('inventory')
            inventory_summary = {}

            for franchise in franchises:
                inventory_summary[franchise.name] = {
                    'distributor_name': user.distributor.name,
                    'inventory': self._format_inventory_data(franchise.inventory.all())
                }

            return Response(inventory_summary)

        elif user.role in ['Franchise', 'Packaging']:
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
    franchise = django_filters.CharFilter(
        field_name="franchise__id", lookup_expr='exact')
    distributor = django_filters.CharFilter(
        field_name="distributor__id", lookup_expr='exact')
    sales_person = django_filters.CharFilter(
        field_name="sales_person__id", lookup_expr='exact')
    order_status = django_filters.CharFilter(
        field_name="order_status", lookup_expr='icontains')
    city = django_filters.CharFilter(
        field_name="city", lookup_expr='icontains')
    date = django_filters.DateFilter(field_name="date", lookup_expr='exact')
    payment_method = django_filters.CharFilter(
        field_name="payment_method", lookup_expr='icontains')
    start_date = django_filters.DateFilter(
        field_name="date", lookup_expr='gte')
    end_date = django_filters.DateFilter(field_name="date", lookup_expr='lte')
    oil_type = django_filters.CharFilter(
        field_name="order_products__product__product__name", lookup_expr='icontains')
    delivery_type = django_filters.CharFilter(
        field_name="delivery_type", lookup_expr='icontains')
    logistics = django_filters.CharFilter(
        field_name="logistics__id", lookup_expr='exact')

    class Meta:
        model = Order
        fields = ['distributor', 'sales_person', 'order_status',
                  'date', 'start_date', 'end_date', 'city', 'oil_type', 'payment_method', 'delivery_type', 'logistics', 'franchise']


class OrderListCreateView(generics.ListCreateAPIView):
    queryset = Order.objects.all().order_by('-id')
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = OrderFilter
    filter_backends = [DjangoFilterBackend,
                       rest_filters.SearchFilter, rest_filters.OrderingFilter]
    search_fields = ['phone_number', 'full_name']
    ordering_fields = ['__all__']
    pagination_class = CustomPagination
    parser_classes = (JSONParser, FormParser, MultiPartParser)

    def create(self, request, *args, **kwargs):
        try:
            # Handle both form-data and raw JSON formats
            data = request.data.copy()
            order_products = []

            # Check if order_products is already a list (JSON payload)
            if isinstance(request.data.get('order_products'), list):
                order_products = request.data.get('order_products')
            # Check if it's form-data format
            elif hasattr(request.data, 'getlist'):
                # Get the order_products string and convert it to list
                order_products_str = request.data.get('order_products')
                if order_products_str:
                    try:
                        # Handle string format "[{"product_id": 39, "quantity": 1}]"
                        import json
                        order_products = json.loads(order_products_str)
                    except json.JSONDecodeError:
                        return Response(
                            {"error": "Invalid order_products format"},
                            status=status.HTTP_400_BAD_REQUEST
                        )

            # Validate order products
            if not order_products:
                return Response(
                    {"error": "At least one product is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create the modified data dictionary
            modified_data = {
                'full_name': request.data.get('full_name'),
                'city': request.data.get('city'),
                'delivery_address': request.data.get('delivery_address'),
                'landmark': request.data.get('landmark'),
                'phone_number': request.data.get('phone_number'),
                'alternate_phone_number': request.data.get('alternate_phone_number'),
                'delivery_charge': request.data.get('delivery_charge'),
                'payment_method': request.data.get('payment_method'),
                'total_amount': request.data.get('total_amount'),
                'promo_code': request.data.get('promo_code'),
                'remarks': request.data.get('remarks'),
                'prepaid_amount': request.data.get('prepaid_amount'),
                'delivery_type': request.data.get('delivery_type'),
                'force_order': request.data.get('force_order'),
                'logistics': request.data.get('logistics'),
                'dash_location': request.data.get('dash_location'),
                'order_products': order_products
            }

            # Handle payment screenshot file
            if 'payment_screenshot' in request.FILES:
                modified_data['payment_screenshot'] = request.FILES['payment_screenshot']
            elif request.data.get('payment_screenshot'):
                # Handle base64 image data
                modified_data['payment_screenshot'] = request.data.get(
                    'payment_screenshot')

            # Update the request data
            request._full_data = modified_data

            # Call the parent create method
            return super().create(request, *args, **kwargs)
        except serializers.ValidationError as exc:
            # Check for your specific error
            error_detail = exc.detail
            if (
                isinstance(error_detail, dict)
                and error_detail.get("status") == status.HTTP_403_FORBIDDEN
            ):
                return Response(error_detail, status=status.HTTP_403_FORBIDDEN)
            # Otherwise, return as 400
            return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)

    def get_queryset(self):
        user = self.request.user
        if user.role == 'Distributor':
            return Order.objects.filter(distributor=user.distributor).order_by('-id')
        elif user.role == 'SalesPerson':
            return Order.objects.filter(sales_person=user).order_by('-id')
        elif user.role == 'Franchise':
            return Order.objects.filter(franchise=user.franchise).order_by('-id')
        elif user.role == 'SuperAdmin':
            return Order.objects.filter(factory=user.factory).order_by('-id')
        elif user.role == 'Packaging':
            return Order.objects.filter(franchise=user.franchise, order_status__in=['Pending', 'Processing', 'Sent to Dash', 'Delivered']).order_by('-id')
        return Order.objects.none()

    def perform_create(self, serializer):
        salesperson = self.request.user
        phone_number = self.request.data.get('phone_number')
        order_products_data = self.request._full_data.get('order_products', [])
        payment_method = self.request.data.get('payment_method')

        # Get force_order flag from request data (default to False if not provided)
        force_order = self.request._full_data.get('force_order', False)
        if isinstance(force_order, str):
            # Convert string to bool if needed (e.g., from form-data)
            force_order = force_order.lower() in ['true', '1', 'yes', 'y']

        if not force_order:
            # Check for recent orders with same phone number across ALL orders
            seven_days_ago = timezone.now() - timezone.timedelta(days=7)
            recent_orders = Order.objects.filter(
                phone_number=phone_number,
                created_at__gte=seven_days_ago
            ).exclude(
                order_status__in=['Cancelled', 'Returned By Customer',
                                  'Returned By Dash', 'Delivered', 'Indrive']
            )
            if recent_orders.exists():
                recent_order = recent_orders.first()
                error_details = {
                    "error": f"Customer with phone number {phone_number} has an active order of within the last 7 days.",
                    "status": status.HTTP_403_FORBIDDEN,
                    "existing_order": {
                        "order_id": recent_order.id,
                        "created_at": recent_order.created_at,
                        "salesperson": {
                            "name": recent_order.sales_person.get_full_name() or recent_order.sales_person.first_name,
                            "phone": recent_order.sales_person.phone_number
                        },
                        "location": {
                            "franchise": recent_order.franchise.name if recent_order.franchise else None,
                            "distributor": recent_order.distributor.name if recent_order.distributor else None
                        }
                    }
                }
                raise serializers.ValidationError(error_details)
            # Get all product IDs ordered by this phone number in last 7 days
            recent_product_ids = set(OrderProduct.objects.filter(
                order__in=recent_orders
            ).values_list('product__product__id', flat=True))
        else:
            recent_product_ids = set()

        # Validate all products exist in inventory before proceeding
        for order_product_data in order_products_data:
            product_id = order_product_data.get('product_id')
            try:
                quantity = int(order_product_data.get('quantity', 0))
            except (ValueError, TypeError):
                raise serializers.ValidationError(
                    f"Invalid quantity format for product ID {product_id}")

            try:
                # Get the inventory item based on user role
                if salesperson.role in ['Franchise', 'SalesPerson', 'Packaging']:
                    inventory_item = Inventory.objects.get(
                        id=product_id,
                        franchise=salesperson.franchise
                    )
                elif salesperson.role == 'Distributor':
                    inventory_item = Inventory.objects.get(
                        id=product_id,
                        distributor=salesperson.distributor
                    )
                elif salesperson.role == 'SuperAdmin':
                    inventory_item = Inventory.objects.get(
                        id=product_id,
                        factory=salesperson.factory
                    )

                # Check if there's enough quantity
                if inventory_item.quantity < quantity:
                    raise serializers.ValidationError(
                        f"Insufficient inventory for product {inventory_item.product.name}. "
                        f"Available: {inventory_item.quantity}, Requested: {quantity}"
                    )

            except Inventory.DoesNotExist:
                raise serializers.ValidationError(
                    f"Product with ID {product_id} not found")

        # Set order status to Delivered if payment method is Office Visit
        if payment_method == 'Office Visit':
            serializer.validated_data['order_status'] = 'Delivered'
        elif payment_method == 'Indrive':
            serializer.validated_data['order_status'] = 'Delivered'

        # Create the order based on user role
        if salesperson.role in ['Franchise', 'SalesPerson']:
            order = serializer.save(
                sales_person=salesperson,
                franchise=salesperson.franchise,
                distributor=salesperson.distributor,
                factory=salesperson.factory
            )
        elif salesperson.role == 'Distributor':
            order = serializer.save(
                distributor=salesperson.distributor,
                sales_person=salesperson,
                factory=salesperson.factory
            )
        elif salesperson.role == 'SuperAdmin':
            order = serializer.save(
                factory=salesperson.factory,
                sales_person=salesperson
            )

        # Update inventory after order creation
        for order_product_data in order_products_data:
            product_id = order_product_data.get('product_id')
            quantity = int(order_product_data.get('quantity'))

            # Get the inventory item again
            if salesperson.role in ['Franchise', 'SalesPerson', 'Packaging']:
                inventory_item = Inventory.objects.get(
                    id=product_id,
                    franchise=salesperson.franchise
                )
            elif salesperson.role == 'Distributor':
                inventory_item = Inventory.objects.get(
                    id=product_id,
                    distributor=salesperson.distributor
                )
            elif salesperson.role == 'SuperAdmin':
                inventory_item = Inventory.objects.get(
                    id=product_id,
                    factory=salesperson.factory
                )

            # Update inventory
            old_quantity = inventory_item.quantity
            inventory_item.quantity -= quantity
            inventory_item.save()

            # Create log
            InventoryChangeLog.objects.create(
                inventory=inventory_item,
                user=salesperson,
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

        # Handle order cancellation and returns
        if (
            order.order_status in ["Cancelled",
                                   "Returned By Customer", "Returned By Dash"]
            and previous_status != order.order_status
        ):
            # Restore inventory quantities for each product in the order
            order_products = OrderProduct.objects.filter(
                order=order).select_related('product__product')
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
            # Assuming User is the model for salespersons
            salesperson = User.objects.get(id=salesperson_id)

            # Check if the distributor of the salesperson matches the logged-in distributor
            if salesperson.distributor != distributor:
                return Response({"detail": "You do not have permission to pay this salesperson's commission."}, status=status.HTTP_403_FORBIDDEN)

            commission = Commission.objects.get(
                distributor=distributor, sales_person=salesperson)

            # Logic to mark the commission as paid
            commission.paid = True  # Assuming there's a 'paid' field in the Commission model
            commission.save()  # Save the updated commission record

            # Optionally, update the salesperson's total commission amount
            # Assuming 'amount' is the commission amount
            salesperson.commission_amount += commission.amount
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
            'product__id',  # Add this to get the actual product ID
            'product__name',
            'quantity'
        }

        if include_status:
            base_fields.add('status')

        inventory_data = inventory_queryset.values(*base_fields)

        product_list = []
        for inv in inventory_data:
            product_dict = {
                'inventory_id': inv['id'],
                'product_id': inv['product__id'],  # Use the actual product ID
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

    def get_queryset(self):
        user = self.request.user
        if user.role == 'SuperAdmin':
            return Inventory.objects.filter(factory=user.factory)
        elif user.role == 'Distributor':
            return Inventory.objects.filter(distributor=user.distributor)
        elif user.role in ['Franchise', 'SalesPerson', 'Packaging']:
            return Inventory.objects.filter(franchise=user.franchise)
        return Inventory.objects.none()

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
            logs = InventoryChangeLog.objects.filter(
                inventory__id=inventory_pk)  # Filter by inventory PK
            return logs
        # Return an empty queryset if 'pk' is not provided
        return InventoryChangeLog.objects.none()


class Inventorylogs(generics.ListAPIView):
    serializer_class = InventoryChangeLogSerializer
    queryset = InventoryChangeLog.objects.all().order_by('-id')
    pagination_class = CustomPagination


class InventoryRequestView(generics.ListCreateAPIView):
    queryset = InventoryRequest.objects.all()
    serializer_class = InventoryRequestSerializer

    def list(self, request, *args, **kwargs):
        user = self.request.user
        queryset = self.get_queryset()

        if user.role == 'SuperAdmin':
            # SuperAdmin can see requests they receive and requests from others
            incoming_requests = []
            franchise_requests = []
            distributor_requests = []

            for request in queryset:
                if request.factory == user.factory:
                    # Requests coming to this factory
                    incoming_requests.append(
                        InventoryRequestSerializer(request).data)
                elif request.user.role == 'Franchise':
                    # Requests made by franchises
                    franchise_requests.append(
                        InventoryRequestSerializer(request).data)
                elif request.user.role == 'Distributor':
                    # Requests made by distributors
                    distributor_requests.append(
                        InventoryRequestSerializer(request).data)

            return Response({
                'incoming_requests': incoming_requests,
                'franchise_requests': franchise_requests,
                'distributor_requests': distributor_requests
            })

        elif user.role == 'Distributor':
            # Distributor can see their own requests and requests they receive
            incoming_requests = []
            outgoing_requests = []

            for request in queryset:
                if request.distributor == user.distributor:
                    # Requests coming to this distributor
                    incoming_requests.append(
                        InventoryRequestSerializer(request).data)
                elif request.user.distributor == user.distributor:
                    # Requests made by this distributor
                    outgoing_requests.append(
                        InventoryRequestSerializer(request).data)

            return Response({
                'incoming_requests': incoming_requests,
                'outgoing_requests': outgoing_requests
            })

        elif user.role == 'Franchise':
            # Franchise can see their own requests and requests they receive
            incoming_requests = []
            outgoing_requests = []

            for request in queryset:
                if request.franchise == user.franchise:
                    # Requests coming to this franchise
                    incoming_requests.append(
                        InventoryRequestSerializer(request).data)
                elif request.user.franchise == user.franchise:
                    # Requests made by this franchise
                    outgoing_requests.append(
                        InventoryRequestSerializer(request).data)

            return Response({
                'incoming_requests': incoming_requests,
                'outgoing_requests': outgoing_requests
            })

        # Return an empty Response for non-authorized users
        return Response([])

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
    filter_backends = [DjangoFilterBackend,
                       rest_filters.SearchFilter, rest_filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name', 'id']
    pagination_class = CustomPagination

    def perform_create(self, serializer):
        user = self.request.user
        if user.role != 'SuperAdmin':
            raise serializers.ValidationError(
                "Only SuperAdmin can create products")
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
        # Define excluded statuses
        excluded_statuses = [
            'Cancelled', 'Returned By Customer', 'Returned By Dash', 'Return Pending']

        # Calculate yesterday's date
        yesterday = today - timezone.timedelta(days=1)

        # Get today's stats - no exclusions
        daily_stats = queryset.filter(date=today).exclude(
            order_status__in=excluded_statuses
        ).aggregate(
            total_orders=Count('id'),
            total_sales=Sum('total_amount')
        )

        # Get yesterday's stats - no exclusions
        yesterday_stats = queryset.filter(date=yesterday).exclude(
            order_status__in=excluded_statuses
        ).aggregate(
            total_orders=Count('id'),
            total_sales=Sum('total_amount')
        )

        # Get all-time stats with status breakdown
        all_time_stats = queryset.aggregate(
            # Active orders and sales
            all_time_orders=Count('id', filter=~Q(
                order_status__in=excluded_statuses)),
            all_time_sales=Sum('total_amount', filter=~Q(
                order_status__in=excluded_statuses), default=0),

            # Cancelled orders and sales totals
            cancelled_orders_count=Count('id', filter=Q(
                order_status__in=excluded_statuses)),
            all_time_cancelled_sales=Sum('total_amount', filter=Q(
                order_status__in=excluded_statuses), default=0),

            # Status-specific counts for active orders
            pending_count=Count('id', filter=Q(order_status='Pending')),
            processing_count=Count('id', filter=Q(order_status='Processing')),
            sent_to_dash_count=Count(
                'id', filter=Q(order_status='Sent to Dash')),
            delivered_count=Count('id', filter=Q(order_status='Delivered')),
            indrive_count=Count('id', filter=Q(order_status='Indrive')),

            # Status-specific counts and amounts for cancelled orders
            cancelled_count=Count('id', filter=Q(order_status='Cancelled')),
            cancelled_amount=Sum('total_amount', filter=Q(
                order_status='Cancelled'), default=0),

            returned_by_customer_count=Count(
                'id', filter=Q(order_status='Returned By Customer')),
            returned_by_customer_amount=Sum('total_amount', filter=Q(
                order_status='Returned By Customer'), default=0),

            returned_by_dash_count=Count(
                'id', filter=Q(order_status='Returned By Dash')),
            returned_by_dash_amount=Sum('total_amount', filter=Q(
                order_status='Returned By Dash'), default=0),

            return_pending_count=Count(
                'id', filter=Q(order_status='Return Pending')),
            return_pending_amount=Sum('total_amount', filter=Q(
                order_status='Return Pending'), default=0)
        )

        return {
            'date': today,
            'total_orders': daily_stats['total_orders'] or 0,
            'total_sales': daily_stats['total_sales'] or 0,
            'total_orders_yesterday': yesterday_stats['total_orders'] or 0,
            'total_sales_yesterday': yesterday_stats['total_sales'] or 0,
            'all_time_orders': all_time_stats['all_time_orders'] or 0,
            'cancelled_orders_count': all_time_stats['cancelled_orders_count'] or 0,
            'cancelled_orders': {
                'cancelled': all_time_stats['cancelled_count'] or 0,
                'returned_by_customer': all_time_stats['returned_by_customer_count'] or 0,
                'returned_by_dash': all_time_stats['returned_by_dash_count'] or 0,
                'return_pending': all_time_stats['return_pending_count'] or 0
            },
            'all_time_sales': float(all_time_stats['all_time_sales'] or 0),
            'all_time_cancelled_sales': float(all_time_stats['all_time_cancelled_sales'] or 0),
            'cancelled_amount': {
                'cancelled': float(all_time_stats['cancelled_amount'] or 0),
                'returned_by_customer': float(all_time_stats['returned_by_customer_amount'] or 0),
                'returned_by_dash': float(all_time_stats['returned_by_dash_amount'] or 0),
                'return_pending': float(all_time_stats['return_pending_amount'] or 0)
            }
        }

    def get(self, request):
        franchise = self.request.query_params.get('franchise')
        distributor = self.request.query_params.get('distributor')
        user = self.request.user
        today = timezone.now().date()

        if user.role == 'SuperAdmin':
            if franchise:
                queryset = Order.objects.filter(franchise=franchise)
            elif distributor:
                queryset = Order.objects.filter(distributor=distributor)
            else:
                queryset = Order.objects.filter(factory=user.factory)
        elif user.role == 'Distributor':
            franchises = Franchise.objects.filter(distributor=user.distributor)
            queryset = Order.objects.filter(franchise__in=franchises)
        elif user.role in ['Franchise', 'Packaging']:
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
    pagination_class = CustomPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if user.role == 'SuperAdmin':
            # Get logs for factory inventory
            # return InventoryChangeLog.objects.filter(
            #     inventory__factory=user.factory
            # ).order_by('-id')
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

        # Return empty queryset for unknown roles
        return InventoryChangeLog.objects.none()


class TopSalespersonView(generics.ListAPIView):
    serializer_class = TopSalespersonSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        franchise = self.request.query_params.get('franchise')
        distributor = self.request.query_params.get('distributor')
        user = self.request.user
        filter_type = self.request.GET.get('filter')
        current_date = timezone.now()

        # Define excluded statuses
        excluded_statuses = [
            'Cancelled', 'Returned By Customer', 'Returned By Dash', 'Return Pending']

        if user.role == 'SuperAdmin':
            if franchise:
                salespersons = CustomUser.objects.filter(
                    role='SalesPerson', franchise=franchise)
            elif distributor:
                salespersons = CustomUser.objects.filter(
                    role='SalesPerson', distributor=distributor)
            else:
                salespersons = CustomUser.objects.filter(
                    factory=user.factory, role='SalesPerson')
        elif user.role == 'Distributor':
            franchises = Franchise.objects.filter(distributor=user.distributor)
            salespersons = CustomUser.objects.filter(
                role='SalesPerson', franchise__in=franchises)
        elif user.role in ['Franchise', 'SalesPerson', 'Packaging']:
            salespersons = CustomUser.objects.filter(
                role='SalesPerson', franchise=user.franchise)
        else:
            return CustomUser.objects.none()

        if filter_type:
            if filter_type == 'daily':
                start_date = current_date.date()
                orders_filter = {
                    'orders__date': start_date,
                }
            elif filter_type == 'weekly':
                start_date = current_date - timezone.timedelta(days=7)
                orders_filter = {
                    'orders__date__gte': start_date,
                }
            elif filter_type == 'monthly':
                # Filter for current month only
                orders_filter = {
                    'orders__date__year': current_date.year,
                    'orders__date__month': current_date.month,
                }
            else:
                orders_filter = {}
        else:
            orders_filter = {}

        # Create base queryset with time filters
        salespersons = salespersons.annotate(
            sales_count=Count('orders', filter=models.Q(
                **orders_filter) & ~models.Q(orders__order_status__in=excluded_statuses)),
            total_sales=Sum('orders__total_amount',
                            filter=models.Q(**orders_filter) & ~models.Q(orders__order_status__in=excluded_statuses))
        ).filter(
            sales_count__gt=0,
            total_sales__gt=0
        ).order_by('-sales_count', '-total_sales')

        return salespersons

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data

        filter_type = request.GET.get('filter', 'all')
        current_date = timezone.now()

        # Define excluded statuses
        excluded_statuses = [
            'Cancelled', 'Returned By Customer', 'Returned By Dash', 'Return Pending']

        for index, item in enumerate(data):
            salesperson = queryset[index]

            orders_query = Order.objects.filter(
                sales_person=salesperson
            ).exclude(order_status__in=excluded_statuses)

            if filter_type == 'daily':
                orders_query = orders_query.filter(
                    date=current_date.date())
            elif filter_type == 'weekly':
                orders_query = orders_query.filter(
                    date__gte=current_date - timezone.timedelta(days=7)
                )
            elif filter_type == 'monthly':
                # Filter for current month only
                orders_query = orders_query.filter(
                    date__year=current_date.year,
                    date__month=current_date.month
                )

            product_sales = (
                OrderProduct.objects.filter(order__in=orders_query)
                .values(
                    'product__product__id',
                    'product__product__name'
                )
                .annotate(
                    total_quantity=Sum('quantity'),
                    total_amount=Sum(
                        models.F('quantity') * models.F('order__total_amount') /
                        models.Subquery(
                            OrderProduct.objects.filter(
                                order=models.OuterRef('order')
                            ).values('order')
                            .annotate(total_qty=Sum('quantity'))
                            .values('total_qty')[:1]
                        )
                    )
                )
                .order_by('-total_quantity')
            )

            item['sales_count'] = queryset[index].sales_count
            item['total_sales'] = float(queryset[index].total_sales)
            item['product_sales'] = [{
                'product_name': p['product__product__name'],
                'quantity_sold': p['total_quantity'],
            } for p in product_sales]

        response_data = {
            'filter_type': filter_type,
            'results': data
        }

        return Response(response_data)


class RevenueView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        franchise = self.request.query_params.get('franchise')
        distributor = self.request.query_params.get('distributor')
        user = self.request.user
        filter_type = request.GET.get(
            'filter', 'monthly')  # Default to monthly
        today = timezone.now().date()

        # Define excluded statuses
        excluded_statuses = [
            'Cancelled', 'Returned By Customer', 'Returned By Dash', 'Return Pending']

        try:
            # Base queryset based on user role
            if user.role == 'SuperAdmin':
                if franchise:
                    base_queryset = Order.objects.filter(franchise=franchise)
                elif distributor:
                    base_queryset = Order.objects.filter(
                        distributor=distributor)
                else:
                    base_queryset = Order.objects.filter(factory=user.factory)
            elif user.role == 'Distributor':
                franchises = Franchise.objects.filter(
                    distributor=user.distributor)
                base_queryset = Order.objects.filter(franchise__in=franchises)
            elif user.role in ['Franchise', 'Packaging']:
                base_queryset = Order.objects.filter(franchise=user.franchise)
            elif user.role == 'SalesPerson':
                base_queryset = Order.objects.filter(sales_person=user)
            else:
                return Response(
                    {"error": "Unauthorized access"},
                    status=status.HTTP_403_FORBIDDEN
                )
            base_queryset = base_queryset.exclude(
                order_status__in=excluded_statuses)

            if filter_type == 'daily':
                revenue = (
                    base_queryset.filter(
                        created_at__year=today.year,
                        created_at__month=today.month
                    )
                    .values('date')
                    .annotate(
                        period=models.F('date'),
                        total_revenue=Sum('total_amount', default=0),
                        order_count=Count('id')
                    )
                    .order_by('date')
                )

            elif filter_type == 'weekly':
                revenue = (
                    base_queryset.filter(created_at__year=today.year)
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
                    base_queryset.annotate(period=TruncYear('created_at'))
                    .values('period')
                    .annotate(
                        total_revenue=Sum('total_amount', default=0),
                        order_count=Count('id')
                    )
                    .order_by('period')
                )

            else:  # Default is monthly
                revenue = (
                    base_queryset.annotate(period=TruncMonth('created_at'))
                    .values('period')
                    .annotate(
                        total_revenue=Sum('total_amount', default=0),
                        order_count=Count('id')
                    )
                    .order_by('period')
                )

            # Format the response data
            response_data = [{
                'period': entry['period'].strftime('%Y-%m-%d') if filter_type == 'daily'
                else entry['period'].strftime(
                    '%Y-%m-%d' if filter_type == 'weekly'
                    else '%Y-%m' if filter_type == 'monthly'
                    else '%Y'
                ),
                'total_revenue': float(entry['total_revenue']),
                'order_count': entry['order_count']
            } for entry in revenue]

            return Response({
                'filter_type': filter_type,
                'user_role': user.role,
                'data': response_data
            })

        except Exception as e:
            return Response(
                {'error': f'Failed to fetch revenue data: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )


class TopProductsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            franchise = self.request.query_params.get('franchise')
            distributor = self.request.query_params.get('distributor')
            user = self.request.user
            filter_type = request.GET.get('filter')
            current_date = timezone.now()

            # Define excluded statuses
            excluded_statuses = [
                'Cancelled', 'Returned By Customer', 'Returned By Dash', 'Return Pending']

            # Base query for order products based on user role
            if user.role == 'SuperAdmin':
                if franchise:
                    base_query = OrderProduct.objects.filter(
                        order__franchise=franchise,
                        order__order_status__in=[
                            'Delivered', 'Pending', 'Indrive', 'Sent to Dash', 'Processing']
                    ).exclude(order__order_status__in=excluded_statuses)
                elif distributor:
                    base_query = OrderProduct.objects.filter(
                        order__distributor=distributor,
                        order__order_status__in=[
                            'Delivered', 'Pending', 'Indrive', 'Sent to Dash', 'Processing']
                    ).exclude(order__order_status__in=excluded_statuses)
                else:
                    base_query = OrderProduct.objects.filter(
                        order__factory=user.factory,
                        order__order_status__in=[
                            'Delivered', 'Pending', 'Indrive', 'Sent to Dash', 'Processing']
                    ).exclude(order__order_status__in=excluded_statuses)
            elif user.role == 'Distributor':
                franchises = Franchise.objects.filter(
                    distributor=user.distributor)
                base_query = OrderProduct.objects.filter(
                    order__franchise__in=franchises,
                    order__order_status__in=[
                        'Delivered', 'Pending', 'Indrive', 'Sent to Dash', 'Processing']
                ).exclude(order__order_status__in=excluded_statuses)
            elif user.role in ['Franchise', 'Packaging']:
                base_query = OrderProduct.objects.filter(
                    order__franchise=user.franchise,
                    order__order_status__in=[
                        'Delivered', 'Pending', 'Indrive', 'Sent to Dash', 'Processing']
                ).exclude(order__order_status__in=excluded_statuses)
            elif user.role == 'SalesPerson':
                base_query = OrderProduct.objects.filter(
                    order__sales_person=user,
                    order__order_status__in=[
                        'Delivered', 'Pending', 'Indrive', 'Sent to Dash', 'Processing']
                ).exclude(order__order_status__in=excluded_statuses)
            else:
                return Response(
                    {"error": "Unauthorized access"},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Apply time filter if specified
            if filter_type:
                if filter_type == 'weekly':
                    # Filter for the last 7 days
                    start_date = current_date - timezone.timedelta(days=7)
                    base_query = base_query.filter(
                        order__created_at__gte=start_date
                    )
                elif filter_type == 'monthly':
                    # Filter for current month only
                    base_query = base_query.filter(
                        order__created_at__year=current_date.year,
                        order__created_at__month=current_date.month
                    )

            # Get top products with aggregated data
            top_products = (
                base_query.values(
                    'product__product__id',
                    'product__product__name'
                ).annotate(
                    total_quantity=Sum('quantity'),
                    total_amount=Sum(
                        models.F('quantity') * models.F('order__total_amount') /
                        models.Subquery(
                            OrderProduct.objects.filter(
                                order=models.OuterRef('order')
                            ).values('order')
                            .annotate(total_qty=Sum('quantity'))
                            .values('total_qty')[:1]
                        )
                    )
                ).order_by('-total_quantity')  # Get top 5 by quantity
            )

            # Format the response data
            response_data = [{
                'product_id': item['product__product__id'],
                'product_name': item['product__product__name'],
                'total_quantity': item['total_quantity'],
                'total_amount': round(float(item['total_amount']), 2) if item['total_amount'] else 0.0
            } for item in top_products]

            return Response({
                'filter_type': filter_type or 'all',
                'user_role': user.role,
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


class DashboardStatsView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        franchise = request.GET.get('franchise')
        distributor = request.GET.get('distributor')
        user = self.request.user
        current_date = timezone.now()
        last_month = current_date - timezone.timedelta(days=30)

        # Define excluded statuses
        excluded_statuses = [
            'Cancelled', 'Returned By Customer', 'Returned By Dash', 'Return Pending']

        # Base queryset filters based on user role
        if user.role == 'SuperAdmin':
            if franchise:
                orders = Order.objects.filter(franchise=franchise)
            elif distributor:
                orders = Order.objects.filter(distributor=distributor)
            else:
                orders = Order.objects.filter(factory=user.factory)
            # For SuperAdmin: all orders, all distributors/franchises as customers, all products
            customers = CustomUser.objects.filter(
                role__in=['Distributor', 'Franchise', 'SalesPerson'],
                is_active=True
            )
            products = Inventory.objects.filter(
                factory=user.factory,
                status='ready_to_dispatch'
            ).values('product').distinct()

        elif user.role == 'Distributor':
            # For Distributor: orders from their franchises, their franchises as customers
            franchises = Franchise.objects.filter(distributor=user.distributor)
            orders = Order.objects.filter(franchise__in=franchises)
            customers = CustomUser.objects.filter(
                franchise__in=franchises,
                is_active=True
            )
            products = Inventory.objects.filter(
                distributor=user.distributor,
                status='ready_to_dispatch'
            ).values('product').distinct()

        elif user.role in ['Franchise', 'SalesPerson', 'Packaging']:
            # For Franchise/SalesPerson: their orders, their sales persons as customers
            orders = Order.objects.filter(franchise=user.franchise)
            customers = CustomUser.objects.filter(
                franchise=user.franchise,
                role='SalesPerson',
                is_active=True
            )
            products = Inventory.objects.filter(
                franchise=user.franchise,
                status='ready_to_dispatch'
            ).values('product').distinct()
        else:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        # Calculate current period stats
        current_revenue = orders.filter(
            created_at__gte=last_month,
            order_status__in=['Delivered', 'Pending',
                              'Indrive', 'Processing', 'Sent to Dash']
        ).exclude(order_status__in=excluded_statuses).aggregate(total=Sum('total_amount'))['total'] or 0

        current_orders = orders.filter(created_at__gte=last_month).exclude(
            order_status__in=excluded_statuses).count()
        current_customers = customers.filter(
            date_joined__gte=last_month).count()
        current_products = products.count()

        # Calculate previous period stats for comparison
        previous_month = last_month - timezone.timedelta(days=30)
        previous_revenue = orders.filter(
            created_at__gte=previous_month,
            created_at__lt=last_month,
            order_status__in=['Delivered', 'Pending',
                              'Indrive', 'Processing', 'Sent to Dash']
        ).exclude(order_status__in=excluded_statuses).aggregate(total=Sum('total_amount'))['total'] or 0

        previous_orders = orders.filter(
            created_at__gte=previous_month,
            created_at__lt=last_month,
            order_status__in=['Delivered', 'Pending',
                              'Indrive', 'Processing', 'Sent to Dash']
        ).exclude(order_status__in=excluded_statuses).count()

        previous_customers = customers.filter(
            date_joined__gte=previous_month,
            date_joined__lt=last_month
        ).count()

        previous_products = Inventory.objects.filter(
            created_at__gte=previous_month,
            created_at__lt=last_month
        ).values('product').distinct().count()

        # Calculate percentage changes
        def calculate_percentage_change(current, previous):
            if previous == 0:
                return 100 if current > 0 else 0
            return ((current - previous) / previous) * 100

        revenue_change = calculate_percentage_change(
            current_revenue, previous_revenue)
        orders_change = calculate_percentage_change(
            current_orders, previous_orders)
        customers_change = calculate_percentage_change(
            current_customers, previous_customers)
        products_change = calculate_percentage_change(
            current_products, previous_products)

        response_data = {
            "total_revenue": {
                "amount": float(current_revenue),
                "percentage_change": round(revenue_change, 1),
                "change_label": "from last month"
            },
            "orders": {
                "count": current_orders,
                "percentage_change": round(orders_change, 1),
                "change_label": "from last month"
            },
            "customers": {
                "count": current_customers,
                "percentage_change": round(customers_change, 1),
                "change_label": "from last month"
            },
            "active_products": {
                "count": current_products,
                "percentage_change": round(products_change, 1),
                "change_label": "from last month"
            }
        }

        return Response(response_data)


class RevenueByProductView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        franchise = request.GET.get('franchise')
        distributor = request.GET.get('distributor')
        user = self.request.user
        # Get filter parameter from query
        filter_type = request.GET.get('filter')
        current_date = timezone.now()

        # Define excluded statuses
        excluded_statuses = [
            'Cancelled', 'Returned By Customer', 'Returned By Dash', 'Return Pending']

        # Filter orders based on user role
        if user.role == 'SuperAdmin':
            if franchise:
                orders = Order.objects.filter(franchise=franchise)
            elif distributor:
                orders = Order.objects.filter(distributor=distributor)
            else:
                orders = Order.objects.filter(
                    order_status__in=['Delivered', 'Pending',
                                      'Indrive', 'Sent to Dash', 'Processing']
                ).exclude(order_status__in=excluded_statuses)
        elif user.role == 'Distributor':
            franchises = Franchise.objects.filter(distributor=user.distributor)
            orders = Order.objects.filter(
                franchise__in=franchises,
                order_status__in=['Delivered', 'Pending',
                                  'Indrive', 'Sent to Dash', 'Processing']
            ).exclude(order_status__in=excluded_statuses)
        elif user.role in ['Franchise', 'SalesPerson', 'Packaging']:
            orders = Order.objects.filter(
                franchise=user.franchise,
                order_status__in=['Delivered', 'Pending',
                                  'Indrive', 'Sent to Dash', 'Processing']
            ).exclude(order_status__in=excluded_statuses)
        else:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        # Apply time filter if specified
        if filter_type:
            if filter_type == 'weekly':
                # Filter for the last 7 days
                start_date = current_date - timezone.timedelta(days=7)
                orders = orders.filter(created_at__gte=start_date)
            elif filter_type == 'monthly':
                # Filter for current month only
                orders = orders.filter(
                    created_at__year=current_date.year,
                    created_at__month=current_date.month
                )

        # Get all order products and calculate revenue per product
        product_revenue = (
            OrderProduct.objects.filter(
                order__in=orders
            ).values(
                'product__product__id',
                'product__product__name'
            ).annotate(
                total_revenue=Sum(
                    models.F('quantity') * models.F('order__total_amount') /
                    models.Subquery(
                        OrderProduct.objects.filter(
                            order=models.OuterRef('order')
                        ).values('order').annotate(
                            total_qty=Sum('quantity')
                        ).values('total_qty')[:1]
                    )
                )
            ).order_by('-total_revenue')
        )

        # Calculate total revenue
        total_revenue = sum(item['total_revenue'] for item in product_revenue)

        # Format the response with percentages
        product_data = []
        for item in product_revenue:
            percentage = (item['total_revenue'] /
                          total_revenue * 100) if total_revenue > 0 else 0
            product_data.append({
                'product_id': item['product__product__id'],
                'product_name': item['product__product__name'],
                'revenue': round(float(item['total_revenue']), 2),
                'percentage': round(percentage, 1)
            })

        # Sort by revenue percentage in descending order
        product_data.sort(key=lambda x: x['percentage'], reverse=True)

        response_data = {
            'total_revenue': round(float(total_revenue), 2),
            'products': product_data,
            'revenue_distribution': {
                'labels': [item['product_name'] for item in product_data],
                'percentages': [item['percentage'] for item in product_data]
            }
        }

        return Response(response_data)


class OrderCSVExportView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get orders based on user role
        user = request.user
        logistics = request.query_params.get('logistics')

        if user.role == 'SuperAdmin':
            orders = Order.objects.filter(
                factory=user.factory)
        elif user.role == 'Distributor':
            franchises = Franchise.objects.filter(distributor=user.distributor)
            orders = Order.objects.filter(
                franchise__in=franchises)
        elif user.role == 'Franchise':
            orders = Order.objects.filter(
                franchise=user.franchise, order_status='Processing').order_by('-id')
        elif user.role == 'Packaging':
            orders = Order.objects.filter(
                franchise=user.franchise, order_status='Processing').order_by('-id')
        else:
            return Response(
                {"error": "Unauthorized to export orders"},
                status=status.HTTP_403_FORBIDDEN
            )
        if logistics:
            orders = orders.filter(logistics=logistics)

        if not orders.exists():
            return Response(
                {"error": "No orders found to export"},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            # Create the HttpResponse object with CSV header
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="orders.csv"'

            # Create CSV writer
            writer = csv.writer(response)

            # Write header row with new fields
            writer.writerow([
                'Customer Name',
                'Contact Number',
                'Alternative Number',
                'Location',
                'Customer Landmark',
                'Address',
                'Customer Order ID',
                'Product Name',
                'Product Price',
                'Payment Type',
                'Client Note'
            ])

            # Write data rows
            for order in orders:
                # Format products string as requested
                products = OrderProduct.objects.filter(order=order)
                products_str = ','.join([
                    f"{p.quantity}-{p.product.product.name}"
                    for p in products
                ])

                # Calculate product price
                product_price = order.total_amount
                if order.prepaid_amount:
                    product_price = order.total_amount - order.prepaid_amount

                # Determine payment type
                payment_type = "pre-paid" if order.prepaid_amount and (
                    order.total_amount - order.prepaid_amount) == 0 else "cashOnDelivery"

                writer.writerow([
                    order.full_name,  # Customer Name
                    order.phone_number,  # Contact Number
                    order.alternate_phone_number or '',  # Alternative Number
                    order.dash_location.name if order.dash_location else '',
                    '',
                    order.delivery_address,  # Address
                    '',
                    products_str,  # Product Name
                    product_price,  # Product Price
                    payment_type,  # Payment Type
                    order.remarks or ''  # Client Note
                ])

            # After successful export, update all processed orders to "Sent to Dash"
            orders.update(order_status='Sent to Dash')

            return response

        except Exception as e:
            return Response(
                {"error": f"Failed to export orders: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PromoCodeListCreateView(generics.ListCreateAPIView):
    queryset = PromoCode.objects.all()
    serializer_class = PromoCodeSerializer

    def get_queryset(self):
        # user = self.request.user
        user = CustomUser.objects.get(id=1)
        if user.role == 'SuperAdmin':
            return PromoCode.objects.all()
        return PromoCode.objects.filter(is_active=True, valid_from__lte=timezone.now(), valid_until__gte=timezone.now())


class PromoCodeDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PromoCode.objects.all()
    serializer_class = PromoCodeSerializer


class ValidatePromoCodeView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        promo_code = request.data.get('promo_code')
        if not promo_code:
            return Response({"error": "Promo code is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            promo_code_instance = PromoCode.objects.get(
                code=promo_code,
                is_active=True,
                valid_from__lte=timezone.now(),
                valid_until__gte=timezone.now()
            )
            if promo_code_instance.max_uses and promo_code_instance.times_used >= promo_code_instance.max_uses:
                return Response({"error": "Promo code has reached its maximum usage limit"}, status=status.HTTP_400_BAD_REQUEST)

            return Response({
                'valid': True,
                'code': promo_code_instance.code,
                'discount_percentage': promo_code_instance.discount_percentage,
                'message': 'Promo code applied successfully'
            })

        except PromoCode.DoesNotExist:
            return Response({"error": "Invalid promo code"}, status=status.HTTP_400_BAD_REQUEST)


class OrderDetailUpdateView(generics.RetrieveUpdateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = (JSONParser, FormParser, MultiPartParser)

    def get_queryset(self):
        """Filter orders based on user role"""
        user = self.request.user
        if user.role == 'SuperAdmin':
            return Order.objects.filter(factory=user.factory)
        elif user.role == 'Distributor':
            return Order.objects.filter(distributor=user.distributor)
        elif user.role in ['Franchise', 'SalesPerson', 'Packaging']:
            return Order.objects.filter(franchise=user.franchise)
        return Order.objects.none()

    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            # Create a dictionary only with fields that are actually provided in the request
            modified_data = {}

            # Handle order products separately
            order_products = None

            if 'logistics' in request.data:
                modified_data['logistics'] = request.data.get('logistics')

            # Check if order_products is provided and parse it
            if 'order_products' in request.data:
                if isinstance(request.data.get('order_products'), list):
                    order_products = request.data.get('order_products')
                elif hasattr(request.data, 'getlist'):
                    order_products_str = request.data.get('order_products')
                    if order_products_str:
                        try:
                            import json
                            order_products = json.loads(order_products_str)
                        except json.JSONDecodeError:
                            return Response(
                                {"error": "Invalid order_products format"},
                                status=status.HTTP_400_BAD_REQUEST
                            )

            # Only include fields that are actually provided in the request
            fields_to_check = [
                'full_name', 'city', 'delivery_address', 'landmark',
                'phone_number', 'alternate_phone_number', 'delivery_charge',
                'payment_method', 'total_amount', 'promo_code', 'remarks', 'dash_location',
                'prepaid_amount', 'delivery_type', 'created_at', 'updated_at',
            ]

            for field in fields_to_check:
                if field in request.data:
                    modified_data[field] = request.data.get(field)

            # Handle payment screenshot if provided
            if 'payment_screenshot' in request.FILES:
                modified_data['payment_screenshot'] = request.FILES['payment_screenshot']
            elif request.data.get('payment_screenshot'):
                modified_data['payment_screenshot'] = request.data.get(
                    'payment_screenshot')

            # Validate promo code if provided
            if 'promo_code' in modified_data:
                promo_code = modified_data['promo_code']
                try:
                    promo_code_instance = PromoCode.objects.get(
                        code=promo_code,
                        is_active=True,
                        valid_from__lte=timezone.now(),
                        valid_until__gte=timezone.now()
                    )
                    if promo_code_instance.max_uses and promo_code_instance.times_used >= promo_code_instance.max_uses:
                        return Response(
                            {"error": "Promo code has reached its maximum usage limit"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                except PromoCode.DoesNotExist:
                    return Response(
                        {"error": "Invalid promo code"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # If someone tries to update the status, return an error
            if 'order_status' in request.data:
                return Response(
                    {"error": "Order status cannot be updated through this endpoint"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Update the instance with only the modified fields
            serializer = self.get_serializer(
                instance,
                data=modified_data,
                partial=True
            )
            serializer.is_valid(raise_exception=True)
            order = serializer.save()

            # Handle order products if provided
            if order_products is not None:
                # Delete existing order products
                instance.order_products.all().delete()
                # Create new order products
                for product_data in order_products:
                    OrderProduct.objects.create(
                        order=instance,
                        product_id=product_data['product_id'],
                        quantity=product_data['quantity']
                    )

            # Update promo code usage if changed and provided
            if 'promo_code' in modified_data and instance.promo_code != promo_code_instance:
                if instance.promo_code:
                    # Decrease usage count of old promo code
                    instance.promo_code.times_used -= 1
                    instance.promo_code.save()

                # Increase usage count of new promo code
                promo_code_instance.times_used += 1
                promo_code_instance.save()

                # Update order's promo code
                instance.promo_code = promo_code_instance
                instance.save()

            return Response(serializer.data)

        except Exception as e:
            return Response(
                {"error": f"Failed to update order: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


class InventoryCheckView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def _get_low_quantity_items(self, inventory_queryset, critical_threshold=50):
        """Helper method to get low quantity items from inventory queryset"""
        low_quantity_items = []
        for item in inventory_queryset:
            if item.quantity < critical_threshold:
                low_quantity_items.append({
                    'product_name': item.product.name,
                    'quantity': item.quantity,
                    'status': 'critical' if item.quantity <= 25 else 'low',
                })
        return sorted(low_quantity_items, key=lambda x: x['quantity'])

    def _format_inventory_response(self, low_quantity_items):
        """Helper method to format inventory response"""
        return {
            'low_quantity_items': low_quantity_items,
            'total_low_items': len(low_quantity_items)
        }

    def _get_inventory_by_owner(self, owner_type, owner):
        """Helper method to get inventory by owner type"""
        return Inventory.objects.filter(**{owner_type: owner})

    def get(self, request):
        franchise = request.query_params.get('franchise')
        distributor = request.query_params.get('distributor')
        user = self.request.user
        critical_threshold = 50

        try:
            if user.role == 'SuperAdmin':
                if franchise:
                    inventory_items = self._get_inventory_by_owner(
                        'franchise', franchise)
                    low_quantity_items = self._get_low_quantity_items(
                        inventory_items, critical_threshold)
                    return Response(self._format_inventory_response(low_quantity_items))
                elif distributor:
                    inventory_items = self._get_inventory_by_owner(
                        'distributor', distributor)
                    low_quantity_items = self._get_low_quantity_items(
                        inventory_items, critical_threshold)
                    return Response(self._format_inventory_response(low_quantity_items))

                response_data = {
                    'factory': {'low_quantity_items': [], 'total_low_items': 0},
                    'distributors': {},
                    'franchises': {}
                }

                # Get factory inventory
                factory_inventory = self._get_inventory_by_owner(
                    'factory', user.factory)
                factory_low_items = self._get_low_quantity_items(
                    factory_inventory, critical_threshold)
                response_data['factory'].update(
                    self._format_inventory_response(factory_low_items))

                # Get distributor inventory
                for dist in Distributor.objects.all():
                    dist_inventory = self._get_inventory_by_owner(
                        'distributor', dist)
                    dist_low_items = self._get_low_quantity_items(
                        dist_inventory, critical_threshold)
                    if dist_low_items:
                        response_data['distributors'][dist.name] = self._format_inventory_response(
                            dist_low_items)

                # Get franchise inventory
                for fran in Franchise.objects.all():
                    fran_inventory = self._get_inventory_by_owner(
                        'franchise', fran)
                    fran_low_items = self._get_low_quantity_items(
                        fran_inventory, critical_threshold)
                    if fran_low_items:
                        response_data['franchises'][fran.name] = self._format_inventory_response(
                            fran_low_items)

                return Response(response_data)

            elif user.role == 'Distributor':
                inventory_items = self._get_inventory_by_owner(
                    'distributor', user.distributor)
                low_quantity_items = self._get_low_quantity_items(
                    inventory_items, critical_threshold)
                return Response(self._format_inventory_response(low_quantity_items))

            elif user.role in ['Franchise', 'SalesPerson', 'Packaging']:
                inventory_items = self._get_inventory_by_owner(
                    'franchise', user.franchise)
                low_quantity_items = self._get_low_quantity_items(
                    inventory_items, critical_threshold)
                return Response(self._format_inventory_response(low_quantity_items))

            else:
                return Response(
                    {"error": "Unauthorized access"},
                    status=status.HTTP_403_FORBIDDEN
                )

        except Exception as e:
            return Response(
                {'error': f'Failed to check inventory: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )


class SalesPersonStatisticsView(APIView):

    def get(self, request, phone_number):

        excluded_statuses = [
            'Cancelled', 'Returned By Customer', 'Returned By Dash', 'Return Pending']

        try:
            # Get the salesperson
            salesperson = CustomUser.objects.get(phone_number=phone_number)

            # Check if the user is a salesperson
            if salesperson.role != 'SalesPerson':
                return Response(
                    {'error': 'User is not a salesperson'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Get filter type and specific date from query params
            filter_type = request.query_params.get('filter', 'all')
            specific_date = request.query_params.get('date')
            end_date = request.query_params.get('end_date')

            # Base queryset for orders
            orders = Order.objects.filter(sales_person=salesperson)

            # Apply specific date filter if provided
            if specific_date and not end_date:
                try:
                    specific_date = datetime.strptime(
                        specific_date, '%Y-%m-%d').date()
                    orders = orders.filter(created_at__date=specific_date)
                except ValueError:
                    return Response(
                        {'error': 'Invalid date format. Use YYYY-MM-DD'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            elif specific_date and end_date:
                try:
                    specific_date = datetime.strptime(
                        specific_date, '%Y-%m-%d').date()
                    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                    orders = orders.filter(
                        created_at__date__gte=specific_date, created_at__date__lte=end_date)
                except ValueError:
                    return Response(
                        {'error': 'Invalid date format. Use YYYY-MM-DD'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            # Apply time filter if no specific date is provided
            elif filter_type == 'daily':
                orders = orders.filter(created_at__date=timezone.now().date())
            elif filter_type == 'weekly':
                orders = orders.filter(
                    created_at__gte=timezone.now() - timezone.timedelta(days=7))
            elif filter_type == 'monthly':
                orders = orders.filter(
                    created_at__gte=timezone.now() - timezone.timedelta(days=30))

            # Calculate total orders and amount
            total_orders = orders.exclude(
                order_status__in=excluded_statuses).count()
            total_cancelled_orders = orders.filter(
                order_status__in=excluded_statuses).count()
            total_amount = orders.exclude(order_status__in=excluded_statuses).aggregate(
                total=Sum('total_amount'))['total'] or 0
            total_cancelled_amount = orders.filter(order_status__in=excluded_statuses).aggregate(
                total=Sum('total_amount'))['total'] or 0
            total_delivery_charge = orders.exclude(order_status__in=excluded_statuses).aggregate(
                total=Sum('delivery_charge'))['total'] or 0
            total_cancelled_delivery_charge = orders.filter(order_status__in=excluded_statuses).aggregate(
                total=Sum('delivery_charge'))['total'] or 0

            # Get product-wise sales data
            product_sales = (
                OrderProduct.objects.filter(order__in=orders.exclude(
                    order_status__in=excluded_statuses))
                .values(
                    'product__product__id',
                    'product__product__name'
                )
                .annotate(
                    quantity_sold=Sum('quantity')
                )
                .order_by('-quantity_sold')
            )

            # Get product-wise sales data for cancelled orders
            cancelled_product_sales = (
                OrderProduct.objects.filter(order__in=orders.filter(
                    order_status__in=excluded_statuses))
                .values(
                    'product__product__id',
                    'product__product__name'
                )
                .annotate(
                    quantity_sold=Sum('quantity')
                )
                .order_by('-quantity_sold')
            )

            # Prepare response data
            data = {
                'user': salesperson,
                'total_orders': total_orders,
                'total_amount': float(total_amount),
                'total_cancelled_orders': total_cancelled_orders,
                'total_cancelled_amount': float(total_cancelled_amount),
                'total_delivery_charge': float(total_delivery_charge),
                'total_cancelled_delivery_charge': float(total_cancelled_delivery_charge),
                'product_sales': [{
                    'product_name': p['product__product__name'],
                    'quantity_sold': p['quantity_sold']
                } for p in product_sales],
                'cancelled_product_sales': [{
                    'product_name': p['product__product__name'],
                    'quantity_sold': p['quantity_sold']
                } for p in cancelled_product_sales],
            }

            serializer = SalesPersonStatisticsSerializer(data)
            return Response(serializer.data)

        except CustomUser.DoesNotExist:
            return Response(
                {'error': 'Salesperson not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SalesPersonRevenueView(generics.GenericAPIView):
    def get(self, request, phone_number):
        excluded_statuses = [
            'Cancelled', 'Returned By Customer', 'Returned By Dash', 'Return Pending']
        try:
            salesperson = CustomUser.objects.get(phone_number=phone_number)
            if salesperson.role != 'SalesPerson':
                return Response(
                    {'error': 'User is not a salesperson'},
                    status=status.HTTP_403_FORBIDDEN
                )

            filter_type = request.query_params.get('filter', 'daily')
            specific_date = request.query_params.get('date')
            end_date = request.query_params.get('end_date')
            today = timezone.now().date()

            # Base queryset for the specific salesperson
            base_queryset = Order.objects.filter(sales_person=salesperson)

            # Common annotation fields with status-specific counts
            annotation_fields = {
                'total_revenue': Sum('total_amount', filter=~Q(order_status__in=excluded_statuses), default=0),
                'total_cancelled_amount': Sum('total_amount', filter=Q(order_status__in=excluded_statuses), default=0),
                'order_count': Count('id', filter=~Q(order_status__in=excluded_statuses)),
                'cancelled_count': Count('id', filter=Q(order_status__in=excluded_statuses)),
                # Status-specific counts for active orders
                'pending_count': Count('id', filter=Q(order_status='Pending')),
                'processing_count': Count('id', filter=Q(order_status='Processing')),
                'sent_to_dash_count': Count('id', filter=Q(order_status='Sent to Dash')),
                'delivered_count': Count('id', filter=Q(order_status='Delivered')),
                'indrive_count': Count('id', filter=Q(order_status='Indrive')),
                # Status-specific counts for cancelled orders
                'cancelled_status_count': Count('id', filter=Q(order_status='Cancelled')),
                'returned_by_customer_count': Count('id', filter=Q(order_status='Returned By Customer')),
                'returned_by_dash_count': Count('id', filter=Q(order_status='Returned By Dash')),
                'return_pending_count': Count('id', filter=Q(order_status='Return Pending'))
            }

            # Handle date range queries
            if specific_date:
                try:
                    specific_date = datetime.strptime(
                        specific_date, '%Y-%m-%d').date()
                    if end_date:
                        end_date = datetime.strptime(
                            end_date, '%Y-%m-%d').date()
                        date_filter = {'created_at__date__range': (
                            specific_date, end_date)}
                    else:
                        date_filter = {'created_at__date': specific_date}

                    revenue = (
                        base_queryset.filter(**date_filter)
                        .values('created_at__date')
                        .annotate(period=models.F('created_at__date'), **annotation_fields)
                        .order_by('created_at__date')
                    )
                except ValueError:
                    return Response(
                        {'error': 'Invalid date format. Use YYYY-MM-DD'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                # Handle filter type queries
                if filter_type == 'daily':
                    revenue = (
                        base_queryset.filter(
                            created_at__year=today.year,
                            created_at__month=today.month
                        )
                        .values('date')
                        .annotate(period=models.F('date'), **annotation_fields)
                        .order_by('date')
                    )
                elif filter_type == 'weekly':
                    revenue = (
                        base_queryset.filter(created_at__year=today.year)
                        .annotate(period=TruncWeek('created_at'))
                        .values('period')
                        .annotate(**annotation_fields)
                        .order_by('period')
                    )
                elif filter_type == 'monthly':
                    revenue = (
                        base_queryset.annotate(period=TruncMonth('created_at'))
                        .values('period')
                        .annotate(**annotation_fields)
                        .order_by('period')
                    )
                elif filter_type == 'yearly':
                    revenue = (
                        base_queryset.annotate(period=TruncYear('created_at'))
                        .values('period')
                        .annotate(**annotation_fields)
                        .order_by('period')
                    )

            # Format response data with detailed status counts
            response_data = [{
                'period': entry['period'].strftime(
                    '%Y-%m-%d' if filter_type in ['daily', 'weekly'] or specific_date
                    else '%Y-%m' if filter_type == 'monthly'
                    else '%Y'
                ),
                'total_revenue': float(entry['total_revenue']),
                'total_cancelled_amount': float(entry['total_cancelled_amount']),
                'order_count': entry['order_count'],
                'cancelled_count': entry['cancelled_count'],
                'active_orders': {
                    'pending': entry['pending_count'],
                    'processing': entry['processing_count'],
                    'sent_to_dash': entry['sent_to_dash_count'],
                    'delivered': entry['delivered_count'],
                    'indrive': entry['indrive_count']
                },
                'cancelled_orders': {
                    'cancelled': entry['cancelled_status_count'],
                    'returned_by_customer': entry['returned_by_customer_count'],
                    'returned_by_dash': entry['returned_by_dash_count'],
                    'return_pending': entry['return_pending_count']
                }
            } for entry in revenue]

            return Response({
                'filter_type': filter_type,
                'specific_date': specific_date.strftime('%Y-%m-%d') if specific_date else None,
                'data': response_data
            })

        except CustomUser.DoesNotExist:
            return Response(
                {'error': 'Salesperson not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to fetch revenue data: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )


class RevenueWithCancelledView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        franchise = self.request.query_params.get('franchise')
        distributor = self.request.query_params.get('distributor')
        user = self.request.user
        filter_type = request.GET.get('filter', 'daily')  # Default to daily
        today = timezone.now().date()

        # Define active order statuses
        active_statuses = ['Pending', 'Processing',
                           'Sent to Dash', 'Delivered', 'Indrive']
        excluded_statuses = [
            'Cancelled', 'Returned By Customer', 'Returned By Dash', 'Return Pending']

        try:
            # Base queryset based on user role
            if user.role == 'SuperAdmin':
                if franchise:
                    base_queryset = Order.objects.filter(franchise=franchise)
                elif distributor:
                    base_queryset = Order.objects.filter(
                        distributor=distributor)
                else:
                    base_queryset = Order.objects.filter(factory=user.factory)
            elif user.role == 'Distributor':
                franchises = Franchise.objects.filter(
                    distributor=user.distributor)
                base_queryset = Order.objects.filter(franchise__in=franchises)
            elif user.role in ['Franchise', 'Packaging']:
                base_queryset = Order.objects.filter(franchise=user.franchise)
            elif user.role == 'SalesPerson':
                base_queryset = Order.objects.filter(sales_person=user)
            else:
                return Response(
                    {"error": "Unauthorized access"},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Common annotation fields with status-specific counts
            annotation_fields = {
                'total_revenue': Sum('total_amount', filter=~Q(order_status__in=excluded_statuses), default=0),
                'total_cancelled_amount': Sum('total_amount', filter=Q(order_status__in=excluded_statuses), default=0),
                'order_count': Count('id', filter=~Q(order_status__in=excluded_statuses)),
                'cancelled_count': Count('id', filter=Q(order_status__in=excluded_statuses)),
                # Status-specific counts for active orders
                'pending_count': Count('id', filter=Q(order_status='Pending')),
                'processing_count': Count('id', filter=Q(order_status='Processing')),
                'sent_to_dash_count': Count('id', filter=Q(order_status='Sent to Dash')),
                'delivered_count': Count('id', filter=Q(order_status='Delivered')),
                'indrive_count': Count('id', filter=Q(order_status='Indrive')),
                # Status-specific counts for cancelled orders
                'cancelled_status_count': Count('id', filter=Q(order_status='Cancelled')),
                'returned_by_customer_count': Count('id', filter=Q(order_status='Returned By Customer')),
                'returned_by_dash_count': Count('id', filter=Q(order_status='Returned By Dash')),
                'return_pending_count': Count('id', filter=Q(order_status='Return Pending'))
            }

            if filter_type == 'daily':
                revenue = (
                    base_queryset.filter(
                        created_at__year=today.year,
                        created_at__month=today.month
                    )
                    .values('date')
                    .annotate(period=models.F('date'), **annotation_fields)
                    .order_by('date')
                )
            elif filter_type == 'weekly':
                revenue = (
                    base_queryset.filter(created_at__year=today.year)
                    .annotate(period=TruncWeek('created_at'))
                    .values('period')
                    .annotate(**annotation_fields)
                    .order_by('period')
                )
            elif filter_type == 'monthly':
                revenue = (
                    base_queryset.annotate(period=TruncMonth('created_at'))
                    .values('period')
                    .annotate(**annotation_fields)
                    .order_by('period')
                )
            elif filter_type == 'yearly':
                revenue = (
                    base_queryset.annotate(period=TruncYear('created_at'))
                    .values('period')
                    .annotate(**annotation_fields)
                    .order_by('period')
                )

            # Format response data with detailed status counts
            response_data = [{
                'period': entry['period'].strftime(
                    '%Y-%m-%d' if filter_type in ['daily', 'weekly']
                    else '%Y-%m' if filter_type == 'monthly'
                    else '%Y'
                ),
                'total_revenue': float(entry['total_revenue']),
                'total_cancelled_amount': float(entry['total_cancelled_amount']),
                'order_count': entry['order_count'],
                'cancelled_count': entry['cancelled_count'],
                'active_orders': {
                    'pending': entry['pending_count'],
                    'processing': entry['processing_count'],
                    'sent_to_dash': entry['sent_to_dash_count'],
                    'delivered': entry['delivered_count'],
                    'indrive': entry['indrive_count']
                },
                'cancelled_orders': {
                    'cancelled': entry['cancelled_status_count'],
                    'returned_by_customer': entry['returned_by_customer_count'],
                    'returned_by_dash': entry['returned_by_dash_count'],
                    'return_pending': entry['return_pending_count']
                }
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


class SearchInJSONFieldFilter(DjangoFilterBackend):
    def filter_queryset(self, request, queryset, view):
        search_query = request.query_params.get('search', '').strip().lower()
        if not search_query:
            return queryset

        filtered_queryset = []

        for location in queryset:
            match_in_name = search_query in location.name.lower()
            match_in_coverage = any(search_query in area.lower()
                                    for area in location.coverage_areas)

            if match_in_name or match_in_coverage:
                filtered_queryset.append(location)

        return filtered_queryset


class LocationSearchAPIView(generics.ListAPIView):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    filter_backends = [SearchInJSONFieldFilter]


class LocationUploadView(APIView):
    serializer_class = FileUploadSerializer

    def post(self, request):
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({'error': 'No file provided'}, status=400)

        filename = uploaded_file.name.lower()

        try:
            # Initialize storage for parsed rows
            rows = []
            if filename.endswith('.xlsx'):
                # Read Excel file in-memory
                wb = openpyxl.load_workbook(uploaded_file, read_only=True)
                sheet = wb.active
                headers = [cell.value for cell in sheet[1]]

                loc_idx = headers.index("Location Name")
                area_idx = headers.index("Coverage Area")

                for row in sheet.iter_rows(min_row=2, values_only=True):
                    rows.append([row[loc_idx], row[area_idx]])

            elif filename.endswith('.csv'):
                # Read CSV file in-memory
                decoded_file = uploaded_file.read().decode('utf-8')
                io_string = io.StringIO(decoded_file)
                reader = csv.reader(io_string)
                headers = next(reader)

                loc_idx = headers.index("Location Name")
                area_idx = headers.index("Coverage Area")

                for row in reader:
                    rows.append([row[loc_idx], row[area_idx]])

            else:
                return Response({'error': 'Unsupported file type. Use .xlsx or .csv'}, status=400)

        except Exception as e:
            return Response({'error': f"Failed to process file: {str(e)}"}, status=400)

        # Save to DB
        created, updated = 0, 0
        for location_name, coverage_raw in rows:
            if not location_name or not coverage_raw:
                continue

            location_name = str(location_name).strip()
            coverage_list = [area.strip() for area in str(
                coverage_raw).split(',') if area.strip()]

            location, is_created = Location.objects.get_or_create(
                name=location_name)

            if is_created:
                location.coverage_areas = coverage_list
                created += 1
            else:
                # Merge new areas without duplicates
                merged = list(set(location.coverage_areas + coverage_list))
                if merged != location.coverage_areas:
                    location.coverage_areas = merged
                    updated += 1

            location.save()

        return Response({
            "message": "Upload successful",
            "locations_created": created,
            "locations_updated": updated
        }, status=201)


class SalesPersonOrderCSVExportView(generics.GenericAPIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request, phone_number):
        excluded_statuses = [
            'Cancelled', 'Returned By Customer', 'Returned By Dash', 'Return Pending']

        # Get date range from query parameters
        start_date = request.query_params.get('date')
        end_date = request.query_params.get('end_date')

        if not start_date or not end_date:
            return Response(
                {"error": "Both start_date and end_date are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Convert string dates to datetime objects
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get sales person by phone number
        try:
            salesperson = CustomUser.objects.get(
                phone_number=phone_number, role='SalesPerson')
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "Sales person not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get orders for the sales person within date range
        orders = Order.objects.filter(
            sales_person=salesperson,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).order_by('-id')

        if not orders.exists():
            return Response(
                {"error": "No orders found to export"},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            # Create the HttpResponse object with CSV header
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="orders.csv"'

            # Create CSV writer
            writer = csv.writer(response)

            # Write header row with new fields
            writer.writerow([
                'Date',
                'Customer Name',
                'Contact Number',
                'Alternative Number',
                'Address',
                'Product Name',
                'Product Price',
                'Payment Type',
                'Order Status',
                'Remarks'
            ])

            # Initialize summary variables
            total_orders = 0
            total_amount = 0
            total_cancelled_orders = 0
            total_cancelled_amount = 0
            overall_orders = 0
            overall_amount = 0

            # Write data rows
            for order in orders:
                # Format products string as requested
                products = OrderProduct.objects.filter(order=order)
                products_str = ','.join([
                    f"{p.quantity}-{p.product.product.name}"
                    for p in products
                ])

                # Calculate product price
                product_price = order.total_amount

                overall_orders += 1
                overall_amount += product_price

                # Update summary statistics
                if order.order_status not in excluded_statuses:
                    total_orders += 1
                    total_amount += product_price

                if order.order_status in excluded_statuses:
                    total_cancelled_orders += 1
                    total_cancelled_amount += product_price

                writer.writerow([
                    order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    order.full_name,  # Customer Name
                    order.phone_number,  # Contact Number
                    order.alternate_phone_number or '',  # Alternative Number
                    order.delivery_address,  # Address
                    products_str,  # Product Name
                    # Product Price
                    f'{product_price}',
                    order.payment_method +
                    # Payment Type
                    (f' ({order.prepaid_amount})' if order.prepaid_amount else ''),
                    order.order_status,
                    order.remarks or ''  # Client Note
                ])

            # Add summary statistics
            writer.writerow([])  # Empty row for spacing
            writer.writerow(['Summary Statistics'])
            writer.writerow(['Overall Orders', overall_orders])
            writer.writerow(['Overall Amount', overall_amount])
            writer.writerow(['Total Orders', total_orders])
            writer.writerow(['Total Amount', total_amount])
            writer.writerow(['Total Cancelled Orders', total_cancelled_orders])
            writer.writerow(['Total Cancelled Amount', total_cancelled_amount])

            return response

        except Exception as e:
            return Response(
                {"error": f"Failed to export orders: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
