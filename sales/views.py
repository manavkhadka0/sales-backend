import csv
import io
import json
from datetime import datetime, time

import openpyxl
from django.contrib.auth.models import User
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django_filters import rest_framework as django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters as rest_filters
from rest_framework import generics, serializers, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from account.models import CustomUser, Distributor, Factory, Franchise
from core.middleware import get_current_db_name, set_current_db_name
from logistics.models import AssignOrder
from logistics.utils import create_order_log

from .models import (
    Commission,
    DatabaseMode,
    Inventory,
    InventoryChangeLog,
    InventoryRequest,
    Location,
    Order,
    OrderProduct,
    Product,
    PromoCode,
)
from .serializers import (
    FileUploadSerializer,
    InventoryChangeLogSerializer,
    InventoryRequestSerializer,
    InventorySerializer,
    InventorySnapshotSerializer,
    LocationSerializer,
    OrderSerializer,
    ProductSerializer,
    PromoCodeSerializer,
    RawMaterialSerializer,
)

# Create your views here.


class InventoryListCreateView(generics.ListCreateAPIView):
    serializer_class = InventorySerializer
    permission_classes = [IsAuthenticated]

    def _format_inventory_data(self, inventory_queryset):
        """Helper method to format inventory data consistently"""
        return [
            {
                "id": inventory.id,
                "product_id": inventory.product.id,
                "product": inventory.product.name,
                "quantity": inventory.quantity,
                "status": inventory.status,
            }
            for inventory in inventory_queryset.filter(status="ready_to_dispatch")
        ]

    def _get_franchise_data(self, franchise):
        """Helper method to get franchise inventory data"""
        return {
            "id": franchise.id,
            "inventory": self._format_inventory_data(franchise.inventory.all()),
        }

    def _get_distributor_data(self, distributor):
        """Helper method to get distributor and its franchises inventory data"""
        distributor_data = {
            "id": distributor.id,
            "inventory": self._format_inventory_data(distributor.inventory.all()),
            "franchises": {},
        }

        franchises = Franchise.objects.filter(distributor=distributor)
        for franchise in franchises:
            distributor_data["franchises"][franchise.name] = self._get_franchise_data(
                franchise
            )

        return distributor_data

    def list(self, request, *args, **kwargs):
        user = self.request.user

        if user.role == "SuperAdmin":
            factories = Factory.objects.prefetch_related("inventory")
            inventory_summary = {}

            for factory in factories:
                factory_data = {
                    "id": factory.id,
                    "inventory": self._format_inventory_data(factory.inventory.all()),
                    "distributors": {},
                }

                distributors = Distributor.objects.prefetch_related("inventory")
                for distributor in distributors:
                    factory_data["distributors"][distributor.name] = (
                        self._get_distributor_data(distributor)
                    )

                inventory_summary[factory.name] = factory_data

            return Response(inventory_summary)

        elif user.role == "Distributor":
            inventory_summary = {
                user.distributor.name: self._get_distributor_data(user.distributor)
            }
            return Response(inventory_summary)

        elif user.role in ["Franchise", "Packaging"]:
            inventory_summary = {
                user.franchise.name: self._get_franchise_data(user.franchise)
            }
            return Response(inventory_summary)

        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        user = self.request.user
        product = serializer.validated_data["product"]
        quantity = serializer.validated_data["quantity"]
        status = serializer.validated_data.get("status", None)

        def get_inventory_owner():
            """Helper method to determine inventory owner based on user role"""
            if user.role == "SuperAdmin":
                # SuperAdmin can only add inventory to their own factory
                return user.factory, "factory"

            elif user.role == "Distributor":
                # Distributor can only add inventory to their own distributor account
                return user.distributor, "distributor"

            elif user.role in ["Franchise", "Packaging"]:
                # Franchise and Packaging can only add inventory to their own franchise
                return user.franchise, "franchise"

            raise serializers.ValidationError(
                "User does not have permission to create inventory"
            )

        def update_or_create_inventory(owner, owner_type):
            """Helper method to handle inventory update or creation"""
            filter_kwargs = {f"{owner_type}": owner, "product": product}
            existing_inventory = Inventory.objects.filter(**filter_kwargs).first()

            if existing_inventory:
                # Update existing inventory
                new_quantity = existing_inventory.quantity + quantity
                InventoryChangeLog.objects.create(
                    inventory=existing_inventory,
                    user=user,
                    old_quantity=existing_inventory.quantity,
                    new_quantity=new_quantity,
                    action="update",
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
                    create_kwargs["status"] = status
                inventory = serializer.save(**create_kwargs)
                InventoryChangeLog.objects.create(
                    inventory=inventory,
                    user=user,
                    old_quantity=0,
                    new_quantity=quantity,
                    action="add",
                )
                return inventory

        # Get inventory owner and type, then update or create inventory
        owner, owner_type = get_inventory_owner()
        return update_or_create_inventory(owner, owner_type)


class FactoryInventoryListView(generics.ListAPIView):
    serializer_class = InventorySerializer

    queryset = Inventory.objects.filter(status="ready_to_dispatch")

    def list(self, request, *args, **kwargs):
        user = self.request.user
        if user.role == "SuperAdmin":
            # Get all factories and their inventories
            factories = Factory.objects.prefetch_related("inventory")
            inventory_summary = []
            for factory in factories:
                inventory_summary.append(
                    {
                        "factory": factory.name,
                        "inventory": [
                            {
                                "id": inventory.id,
                                "product_id": inventory.product.id,
                                "product": inventory.product.name,
                                "quantity": inventory.quantity,
                                "status": inventory.status,
                            }
                            for inventory in factory.inventory.all()
                        ],
                    }
                )
            # Return the summary for SuperAdmin
            return Response(inventory_summary)

        return (
            Inventory.objects.none()
        )  # Return an empty queryset for non-SuperAdmin users


class DistributorInventoryListView(generics.ListAPIView):
    serializer_class = InventorySerializer
    queryset = Inventory.objects.all()

    def _format_inventory_data(self, inventory_queryset):
        """Helper method to format inventory data consistently"""
        return [
            {
                "id": inventory.id,
                "product_id": inventory.product.id,
                "product": inventory.product.name,
                "quantity": inventory.quantity,
                "status": inventory.status,
            }
            for inventory in inventory_queryset
        ]

    def _get_distributor_data(self, distributor):
        """Helper method to get distributor inventory data"""
        return {"inventory": self._format_inventory_data(distributor.inventory.all())}

    def list(self, request, *args, **kwargs):
        user = self.request.user

        if user.role == "SuperAdmin":
            distributors = Distributor.objects.filter(
                factory=user.factory
            ).prefetch_related("inventory")
            inventory_summary = {
                distributor.name: self._get_distributor_data(distributor)
                for distributor in distributors
            }
            return Response(inventory_summary)

        elif user.role == "Distributor":
            inventory_summary = {
                user.distributor.name: self._get_distributor_data(user.distributor)
            }
            return Response(inventory_summary)

        elif user.role in ["Franchise", "Packaging"]:
            inventory_summary = {
                user.franchise.name: {
                    "inventory": self._format_inventory_data(
                        user.franchise.inventory.all()
                    )
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
                "id": inventory.id,
                "product_id": inventory.product.id,
                "product": inventory.product.name,
                "quantity": inventory.quantity,
            }
            for inventory in inventory_queryset.filter(status="ready_to_dispatch")
        ]

    def list(self, request, *args, **kwargs):
        user = self.request.user

        if user.role == "SuperAdmin":
            # Get all franchises with their distributors
            franchises = (
                Franchise.objects.filter(distributor__factory=user.factory)
                .prefetch_related("inventory", "distributor")
                .all()
            )
            inventory_summary = {}

            for franchise in franchises:
                inventory_summary[franchise.name] = {
                    "distributor_name": franchise.distributor.name
                    if franchise.distributor
                    else "No Distributor",
                    "inventory": self._format_inventory_data(franchise.inventory.all()),
                }

            return Response(inventory_summary)

        elif user.role == "Distributor":
            # Get franchises under this distributor
            franchises = Franchise.objects.filter(
                distributor=user.distributor
            ).prefetch_related("inventory")
            inventory_summary = {}

            for franchise in franchises:
                inventory_summary[franchise.name] = {
                    "distributor_name": user.distributor.name,
                    "inventory": self._format_inventory_data(franchise.inventory.all()),
                }

            return Response(inventory_summary)

        elif user.role in ["Franchise", "Packaging"]:
            # Get only this franchise's inventory
            inventory_summary = {
                user.franchise.name: {
                    "distributor_name": user.franchise.distributor.name
                    if user.franchise.distributor
                    else "No Distributor",
                    "inventory": self._format_inventory_data(
                        user.franchise.inventory.all()
                    ),
                }
            }
            return Response(inventory_summary)

        return Response({})  # Return empty dict for unauthorized users


class CustomPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class OrderFilter(django_filters.FilterSet):
    franchise = django_filters.CharFilter(
        field_name="franchise__id", lookup_expr="exact"
    )
    distributor = django_filters.CharFilter(
        field_name="distributor__id", lookup_expr="exact"
    )
    sales_person = django_filters.CharFilter(
        field_name="sales_person__id", lookup_expr="exact"
    )
    order_status = django_filters.CharFilter(
        field_name="order_status", lookup_expr="icontains"
    )
    city = django_filters.CharFilter(field_name="city", lookup_expr="icontains")
    date = django_filters.DateFilter(field_name="date", lookup_expr="exact")
    payment_method = django_filters.CharFilter(
        field_name="payment_method", lookup_expr="icontains"
    )
    start_date = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    end_date = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    oil_type = django_filters.CharFilter(
        field_name="order_products__product__product__name", lookup_expr="icontains"
    )
    delivery_type = django_filters.CharFilter(
        field_name="delivery_type", lookup_expr="icontains"
    )
    logistics = django_filters.CharFilter(field_name="logistics", lookup_expr="exact")
    is_assigned = django_filters.BooleanFilter(
        method="filter_by_assigned_status", label="Filter by assignment status"
    )
    is_bulk_order = django_filters.BooleanFilter(method="filter_bulk_orders")

    def filter_by_assigned_status(self, queryset, name, value):
        if value is not None:
            if value:  # If True, return assigned orders
                return queryset.filter(assign_orders__isnull=False)
            # If False, return unassigned orders
            return queryset.filter(assign_orders__isnull=True)
        return queryset

    def filter_bulk_orders(self, queryset, name, value):
        """Filter for bulk orders (orders with >3 quantity of matching products)"""
        if value is None or not value:
            return queryset  # Return all orders if is_bulk_order is False or not set

            # Use default keywords from BulkOrdersView
        product_keywords = "oil bottle"
        keywords_list = [kw.strip().lower() for kw in product_keywords.split(",")]

        keyword_filters = Q()
        for keyword in keywords_list:
            keyword_filters |= Q(
                order_products__product__product__name__icontains=keyword
            )

        annotated_orders = queryset.annotate(
            matching_products_qty=Sum(
                "order_products__quantity", filter=keyword_filters
            )
        )

        # Filter for bulk orders when is_bulk_order=True
        return annotated_orders.filter(matching_products_qty__gte=3)

    class Meta:
        model = Order
        fields = [
            "distributor",
            "sales_person",
            "order_status",
            "date",
            "start_date",
            "end_date",
            "city",
            "oil_type",
            "payment_method",
            "delivery_type",
            "logistics",
            "franchise",
            "is_assigned",
            "is_bulk_order",
        ]


class OrderListCreateView(generics.ListCreateAPIView):
    queryset = Order.objects.all().order_by("-id")
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = OrderFilter
    filter_backends = [
        DjangoFilterBackend,
        rest_filters.SearchFilter,
        rest_filters.OrderingFilter,
    ]
    search_fields = ["phone_number", "full_name", "order_code"]
    ordering_fields = ["__all__"]
    pagination_class = CustomPagination
    parser_classes = (JSONParser, FormParser, MultiPartParser)

    def create(self, request, *args, **kwargs):
        try:
            # Handle both form-data and raw JSON formats
            order_products = []

            # Check if order_products is already a list (JSON payload)
            if isinstance(request.data.get("order_products"), list):
                order_products = request.data.get("order_products")
            # Check if it's form-data format
            elif hasattr(request.data, "getlist"):
                # Get the order_products string and convert it to list
                order_products_str = request.data.get("order_products")
                if order_products_str:
                    try:
                        # Handle string format "[{"product_id": 39, "quantity": 1}]"
                        import json

                        order_products = json.loads(order_products_str)
                    except json.JSONDecodeError:
                        return Response(
                            {"error": "Invalid order_products format"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

            # Validate order products
            if not order_products:
                return Response(
                    {"error": "At least one product is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Create the modified data dictionary
            modified_data = {
                "full_name": request.data.get("full_name"),
                "city": request.data.get("city"),
                "delivery_address": request.data.get("delivery_address"),
                "landmark": request.data.get("landmark"),
                "phone_number": request.data.get("phone_number"),
                "alternate_phone_number": request.data.get("alternate_phone_number"),
                "delivery_charge": request.data.get("delivery_charge"),
                "payment_method": request.data.get("payment_method"),
                "total_amount": request.data.get("total_amount"),
                "promo_code": request.data.get("promo_code"),
                "remarks": request.data.get("remarks"),
                "prepaid_amount": request.data.get("prepaid_amount"),
                "delivery_type": request.data.get("delivery_type"),
                "force_order": request.data.get("force_order"),
                "logistics": request.data.get("logistics"),
                "dash_location": request.data.get("dash_location"),
                "order_products": order_products,
            }

            # Handle payment screenshot file
            if "payment_screenshot" in request.FILES:
                modified_data["payment_screenshot"] = request.FILES[
                    "payment_screenshot"
                ]
            elif request.data.get("payment_screenshot"):
                # Handle base64 image data
                modified_data["payment_screenshot"] = request.data.get(
                    "payment_screenshot"
                )

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
        if user.role == "Distributor":
            return Order.objects.filter(distributor=user.distributor).order_by("-id")
        elif user.role == "SalesPerson":
            return Order.objects.filter(sales_person=user).order_by("-id")
        elif user.role == "Franchise":
            return Order.objects.filter(franchise=user.franchise).order_by("-id")
        elif user.role == "SuperAdmin":
            return Order.objects.filter(factory=user.factory).order_by("-id")
        elif user.role == "Packaging":
            return Order.objects.filter(franchise=user.franchise).order_by("-id")
        elif user.role == "YDM_Rider":
            assigned_order_ids = AssignOrder.objects.filter(user=user).values_list(
                "order_id", flat=True
            )
            return Order.objects.filter(
                id__in=assigned_order_ids,
                logistics="YDM",
            ).order_by("-id")
        elif user.role == "YDM_Logistics":
            return (
                Order.objects.filter(logistics="YDM")
                .order_by("-id")
                .exclude(
                    order_status__in=[
                        "Pending",
                        "Processing",
                        "Sent to Dash",
                        "Indrive",
                        "Return By Dash",
                    ]
                )
            )
        elif user.role == "YDM_Operator":
            return (
                Order.objects.filter(logistics="YDM")
                .order_by("-id")
                .exclude(
                    order_status__in=[
                        "Pending",
                        "Processing",
                        "Sent to Dash",
                        "Indrive",
                        "Return By Dash",
                    ]
                )
            )
        return Order.objects.none()

    def perform_create(self, serializer):
        salesperson = self.request.user
        phone_number = self.request.data.get("phone_number")
        order_products_data = self.request._full_data.get("order_products", [])
        payment_method = self.request.data.get("payment_method")
        prepaid_amount = self.request.data.get("prepaid_amount", 0)

        # Get force_order flag from request data (default to False if not provided)
        force_order = self.request._full_data.get("force_order", False)
        if isinstance(force_order, str):
            # Convert string to bool if needed (e.g., from form-data)
            force_order = force_order.lower() in ["true", "1", "yes", "y"]

        # Check if customer has previously cancelled or returned orders
        cancelled_returned_orders = Order.objects.filter(
            phone_number=phone_number,
            order_status__in=[
                "Cancelled",
                "Returned By Customer",
                "Returned By Dash",
                "Return Pending",
            ],
        ).exists()
        if not force_order and cancelled_returned_orders:
            recent_order = Order.objects.filter(
                phone_number=phone_number,
                order_status__in=[
                    "Cancelled",
                    "Returned By Customer",
                    "Returned By Dash",
                    "Return Pending",
                ],
            ).first()
            # Check if prepaid_amount is provided and is greater than 0
            if not prepaid_amount or float(prepaid_amount) <= 0:
                error_details = {
                    "error": "This customer has previously cancelled or returned orders. Ask For Prepayment before placing a new order or Force Order.",
                    "status": status.HTTP_403_FORBIDDEN,
                    "requires_prepayment": True,
                    "existing_order": {
                        "order_id": recent_order.id,
                        "created_at": recent_order.created_at,
                        "salesperson": {
                            "name": recent_order.sales_person.get_full_name()
                            or recent_order.sales_person.first_name,
                            "phone": recent_order.sales_person.phone_number,
                        },
                        "location": {
                            "franchise": recent_order.franchise.name
                            if recent_order.franchise
                            else None,
                            "distributor": recent_order.distributor.name
                            if recent_order.distributor
                            else None,
                        },
                        "order_status": recent_order.order_status,
                    },
                    "message": "Please ask for prepayment before placing the order for this customer.",
                }
                raise serializers.ValidationError(error_details)

        if not force_order:
            # Check for recent orders with same phone number across ALL orders
            seven_days_ago = timezone.now() - timezone.timedelta(days=7)
            recent_orders = Order.objects.filter(
                phone_number=phone_number, created_at__gte=seven_days_ago
            ).exclude(
                order_status__in=[
                    "Cancelled",
                    "Returned By Customer",
                    "Returned By Dash",
                    "Delivered",
                    "Indrive",
                ]
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
                            "name": recent_order.sales_person.get_full_name()
                            or recent_order.sales_person.first_name,
                            "phone": recent_order.sales_person.phone_number,
                        },
                        "location": {
                            "franchise": recent_order.franchise.name
                            if recent_order.franchise
                            else None,
                            "distributor": recent_order.distributor.name
                            if recent_order.distributor
                            else None,
                        },
                        "order_status": recent_order.order_status,
                    },
                }
                raise serializers.ValidationError(error_details)
            # Get all product IDs ordered by this phone number in last 7 days
            recent_product_ids = set(
                OrderProduct.objects.filter(order__in=recent_orders).values_list(
                    "product__product__id", flat=True
                )
            )
        else:
            recent_product_ids = set()

        # Validate all products exist in inventory before proceeding
        for order_product_data in order_products_data:
            product_id = order_product_data.get("product_id")
            try:
                quantity = int(order_product_data.get("quantity", 0))
            except (ValueError, TypeError):
                raise serializers.ValidationError(
                    f"Invalid quantity format for product ID {product_id}"
                )

            try:
                # Get the inventory item based on user role
                if salesperson.role in ["Franchise", "SalesPerson", "Packaging"]:
                    inventory_item = Inventory.objects.get(
                        id=product_id, franchise=salesperson.franchise
                    )
                elif salesperson.role == "Distributor":
                    inventory_item = Inventory.objects.get(
                        id=product_id, distributor=salesperson.distributor
                    )
                elif salesperson.role == "SuperAdmin":
                    inventory_item = Inventory.objects.get(
                        id=product_id, factory=salesperson.factory
                    )

                # Check if there's enough quantity
                if inventory_item.quantity < quantity:
                    raise serializers.ValidationError(
                        f"Insufficient inventory for product {inventory_item.product.name}. "
                        f"Available: {inventory_item.quantity}, Requested: {quantity}"
                    )

            except Inventory.DoesNotExist:
                raise serializers.ValidationError(
                    f"Product with ID {product_id} not found"
                )

        # Set order status to Delivered if payment method is Office Visit
        if payment_method == "Office Visit":
            serializer.validated_data["order_status"] = "Delivered"
        elif payment_method == "Indrive":
            serializer.validated_data["order_status"] = "Delivered"

        # Create the order based on user role
        if salesperson.role in ["Franchise", "SalesPerson"]:
            order = serializer.save(
                sales_person=salesperson,
                franchise=salesperson.franchise,
                distributor=salesperson.distributor,
                factory=salesperson.factory,
            )
        elif salesperson.role == "Distributor":
            order = serializer.save(
                distributor=salesperson.distributor,
                sales_person=salesperson,
                factory=salesperson.factory,
            )
        elif salesperson.role == "SuperAdmin":
            order = serializer.save(
                factory=salesperson.factory, sales_person=salesperson
            )

        # Update inventory after order creation
        for order_product_data in order_products_data:
            product_id = order_product_data.get("product_id")
            quantity = int(order_product_data.get("quantity"))

            # Get the inventory item again
            if salesperson.role in ["Franchise", "SalesPerson", "Packaging"]:
                inventory_item = Inventory.objects.get(
                    id=product_id, franchise=salesperson.franchise
                )
            elif salesperson.role == "Distributor":
                inventory_item = Inventory.objects.get(
                    id=product_id, distributor=salesperson.distributor
                )
            elif salesperson.role == "SuperAdmin":
                inventory_item = Inventory.objects.get(
                    id=product_id, factory=salesperson.factory
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
                action="order_created",
            )

        return order


class OrderUpdateView(generics.UpdateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def update(self, request, *args, **kwargs):
        order = self.get_object()
        previous_status = order.order_status
        comment = request.data.get("comment", None)
        logistics = request.data.get("logistics", None)
        order_status = request.data.get("order_status", None)

        # -----------------------------------------
        # 1️⃣ HANDLE FREE DELIVERY TOGGLE (+/- 100)
        # -----------------------------------------
        new_is_delivery_free = request.data.get("is_delivery_free", None)

        if new_is_delivery_free is not None:
            # Convert "true"/"false" → boolean
            new_is_delivery_free = str(new_is_delivery_free).lower() in [
                "true",
                "1",
                "yes",
            ]

            # Toggle ON (False → True)
            if new_is_delivery_free and not order.is_delivery_free:
                order.total_amount = order.total_amount - 100

            # Toggle OFF (True → False)
            if not new_is_delivery_free and order.is_delivery_free:
                order.total_amount = order.total_amount + 100

            order.is_delivery_free = new_is_delivery_free
            order.save()

        # -----------------------------------------
        # 2️⃣ LOGISTICS CHANGE LOGIC
        # -----------------------------------------
        if logistics:
            order.logistics = logistics
            if logistics == "YDM":
                order.order_status = "Sent to YDM"
            elif logistics == "DASH" and previous_status == "Sent to YDM":
                order.order_status = "Pending"
            order.save()

        # -----------------------------------------
        # 3️⃣ ORDER STATUS SHORTCUTS
        # -----------------------------------------
        if order_status == "Sent to YDM":
            order.order_status = order_status
            order.logistics = "YDM"
            order.save()
        elif order_status == "Sent to Dash":
            order.order_status = order_status
            order.logistics = "DASH"
            order.save()

        # -----------------------------------------
        # 4️⃣ PERFORM DRF NORMAL UPDATE
        # -----------------------------------------
        response = super().update(request, *args, **kwargs)
        order.refresh_from_db()

        # -----------------------------------------
        # 5️⃣ ORDER STATUS CHANGE LOG ENTRY
        # -----------------------------------------
        new_status = order.order_status
        if new_status != previous_status:
            create_order_log(
                order, previous_status, new_status, user=request.user, comment=comment
            )

        # -----------------------------------------
        # 6️⃣ HANDLE ORDER CANCELLATION / RETURNS
        # -----------------------------------------
        if (
            order.order_status
            in [
                "Cancelled",
                "Returned By Customer",
                "Returned By Dash",
                "Returned By YDM",
            ]
            and previous_status != order.order_status
        ):
            order_products = OrderProduct.objects.filter(order=order).select_related(
                "product__product"
            )

            for order_product in order_products:
                try:
                    inventory = Inventory.objects.get(
                        product__id=order_product.product.product.id,
                        franchise=order.franchise,
                    )
                    old_quantity = inventory.quantity
                    inventory.quantity += order_product.quantity
                    inventory.save()

                    InventoryChangeLog.objects.create(
                        inventory=inventory,
                        user=request.user,
                        old_quantity=old_quantity,
                        new_quantity=inventory.quantity,
                        action="order_cancelled",
                    )
                except Inventory.DoesNotExist:
                    return Response(
                        {
                            "detail": f"Inventory not found for product {order_product.product.product.name}"
                        },
                        status=status.HTTP_400_BAD_REQUEST,
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
                return Response(
                    {
                        "detail": "You do not have permission to pay this salesperson's commission."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            commission = Commission.objects.get(
                distributor=distributor, sales_person=salesperson
            )

            # Logic to mark the commission as paid
            commission.paid = (
                True  # Assuming there's a 'paid' field in the Commission model
            )
            commission.save()  # Save the updated commission record

            # Optionally, update the salesperson's total commission amount
            # Assuming 'amount' is the commission amount
            salesperson.commission_amount += commission.amount
            salesperson.save()  # Save the updated salesperson

            return Response(
                {"detail": "Commission marked as paid."}, status=status.HTTP_200_OK
            )

        except User.DoesNotExist:
            return Response(
                {"detail": "Salesperson not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except Commission.DoesNotExist:
            return Response(
                {"detail": "Commission not found for this salesperson."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer

    def _format_inventory_data(self, inventory_queryset, include_status=False):
        """Helper method to format inventory data consistently"""
        base_fields = {
            "id",
            "product",
            "product__id",  # Add this to get the actual product ID
            "product__name",
            "quantity",
        }

        if include_status:
            base_fields.add("status")

        inventory_data = inventory_queryset.values(*base_fields)

        product_list = []
        for inv in inventory_data:
            product_dict = {
                "inventory_id": inv["id"],
                "product_id": inv["product__id"],  # Use the actual product ID
                "product_name": inv["product__name"],
                "quantity": inv["quantity"],
            }
            if include_status:
                product_dict["status"] = inv["status"]
            product_list.append(product_dict)

        return product_list

    def get_queryset(self):
        user = self.request.user

        if user.role in ["Franchise", "SalesPerson"]:
            return self._format_inventory_data(
                Inventory.objects.filter(franchise=user.franchise)
            )

        elif user.role == "Distributor":
            return self._format_inventory_data(
                Inventory.objects.filter(distributor=user.distributor)
            )

        elif user.role == "SuperAdmin":
            return self._format_inventory_data(
                Inventory.objects.filter(factory=user.factory), include_status=True
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
        if user.role == "SuperAdmin":
            return Inventory.objects.filter(factory=user.factory)
        elif user.role == "Distributor":
            return Inventory.objects.filter(distributor=user.distributor)
        elif user.role in ["Franchise", "SalesPerson", "Packaging"]:
            return Inventory.objects.filter(franchise=user.franchise)
        return Inventory.objects.none()

    def perform_update(self, serializer):
        inventory_item = self.get_object()
        user = self.request.user

        # Retrieve the new quantity from the request data
        new_quantity = self.request.data.get("new_quantity")
        # Create a log entry before updating
        InventoryChangeLog.objects.create(
            inventory=inventory_item,
            user=user,
            old_quantity=inventory_item.quantity,
            new_quantity=new_quantity
            if new_quantity is not None
            else inventory_item.quantity,
            action="update",
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
            action="deleted",
        )

        # Perform the deletion
        instance.delete()


class InventoryChangeLogView(generics.ListAPIView):
    serializer_class = InventoryChangeLogSerializer
    queryset = InventoryChangeLog.objects.all()

    def get_queryset(self):
        # Use 'pk' instead of 'id'
        inventory_pk = self.kwargs.get("pk")
        if inventory_pk is not None:
            logs = InventoryChangeLog.objects.filter(
                inventory__id=inventory_pk
            )  # Filter by inventory PK
            return logs
        # Return an empty queryset if 'pk' is not provided
        return InventoryChangeLog.objects.none()


class Inventorylogs(generics.ListAPIView):
    serializer_class = InventoryChangeLogSerializer
    queryset = InventoryChangeLog.objects.all().order_by("-id")
    pagination_class = CustomPagination


class InventoryRequestView(generics.ListCreateAPIView):
    queryset = InventoryRequest.objects.all()
    serializer_class = InventoryRequestSerializer

    def list(self, request, *args, **kwargs):
        user = self.request.user
        queryset = self.get_queryset()

        if user.role == "SuperAdmin":
            # SuperAdmin can see requests they receive and requests from others
            incoming_requests = []
            franchise_requests = []
            distributor_requests = []

            for request in queryset:
                if request.factory == user.factory:
                    # Requests coming to this factory
                    incoming_requests.append(InventoryRequestSerializer(request).data)
                elif request.user.role == "Franchise":
                    # Requests made by franchises
                    franchise_requests.append(InventoryRequestSerializer(request).data)
                elif request.user.role == "Distributor":
                    # Requests made by distributors
                    distributor_requests.append(
                        InventoryRequestSerializer(request).data
                    )

            return Response(
                {
                    "incoming_requests": incoming_requests,
                    "franchise_requests": franchise_requests,
                    "distributor_requests": distributor_requests,
                }
            )

        elif user.role == "Distributor":
            # Distributor can see their own requests and requests they receive
            incoming_requests = []
            outgoing_requests = []

            for request in queryset:
                if request.distributor == user.distributor:
                    # Requests coming to this distributor
                    incoming_requests.append(InventoryRequestSerializer(request).data)
                elif request.user.distributor == user.distributor:
                    # Requests made by this distributor
                    outgoing_requests.append(InventoryRequestSerializer(request).data)

            return Response(
                {
                    "incoming_requests": incoming_requests,
                    "outgoing_requests": outgoing_requests,
                }
            )

        elif user.role == "Franchise":
            # Franchise can see their own requests and requests they receive
            incoming_requests = []
            outgoing_requests = []

            for request in queryset:
                if request.franchise == user.franchise:
                    # Requests coming to this franchise
                    incoming_requests.append(InventoryRequestSerializer(request).data)
                elif request.user.franchise == user.franchise:
                    # Requests made by this franchise
                    outgoing_requests.append(InventoryRequestSerializer(request).data)

            return Response(
                {
                    "incoming_requests": incoming_requests,
                    "outgoing_requests": outgoing_requests,
                }
            )

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
        total_amount = self.request.data.get("total_amount")
        status = self.request.data.get("status")

        if total_amount is not None:
            serializer.instance.total_amount = total_amount
        if status is not None:
            serializer.instance.status = status

        serializer.save()  # Save the updated instance


class AllProductsListView(generics.ListCreateAPIView):
    serializer_class = ProductSerializer
    queryset = Product.objects.all()
    filter_backends = [
        DjangoFilterBackend,
        rest_filters.SearchFilter,
        rest_filters.OrderingFilter,
    ]
    search_fields = ["name"]
    ordering_fields = ["name", "id"]
    pagination_class = CustomPagination

    def perform_create(self, serializer):
        user = self.request.user
        if user.role != "SuperAdmin":
            raise serializers.ValidationError("Only SuperAdmin can create products")
        serializer.save()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if isinstance(queryset, list):  # If it's our custom product list
            return Response(queryset)
        # Otherwise, use default serializer behavior
        return super().list(request, *args, **kwargs)


class UserInventoryLogFilter(django_filters.FilterSet):
    changed_at = django_filters.CharFilter(
        field_name="changed_at", lookup_expr="icontains"
    )

    class Meta:
        model = InventoryChangeLog
        fields = ["changed_at"]


class UserInventoryLogs(generics.ListAPIView):
    serializer_class = InventoryChangeLogSerializer
    pagination_class = CustomPagination
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = UserInventoryLogFilter

    def get_queryset(self):
        user = self.request.user

        if user.role == "SuperAdmin":
            # Get logs for factory inventory
            # return InventoryChangeLog.objects.filter(
            #     inventory__factory=user.factory
            # ).order_by('-id')
            return InventoryChangeLog.objects.filter(
                inventory__factory=user.factory
            ).order_by("-id")

        elif user.role == "Distributor":
            # Get logs for distributor inventory
            return InventoryChangeLog.objects.filter(
                inventory__distributor=user.distributor
            ).order_by("-id")

        elif user.role == "Franchise":
            # Get logs for franchise inventory
            return InventoryChangeLog.objects.filter(
                inventory__franchise=user.franchise
            ).order_by("-id")

        elif user.role == "SalesPerson":
            # Get logs where the user is the one who made the change
            return InventoryChangeLog.objects.filter(user=user).order_by("-id")

        # Return empty queryset for unknown roles
        return InventoryChangeLog.objects.none()


class RawMaterialListView(generics.ListAPIView):
    serializer_class = RawMaterialSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        # Only SuperAdmin can access raw materials
        if user.role == "SuperAdmin":
            return Inventory.objects.filter(factory=user.factory, status="raw_material")

        # Return empty queryset for all other roles
        return Inventory.objects.none()

    def list(self, request, *args, **kwargs):
        if request.user.role != "SuperAdmin":
            return Response(
                {"detail": "Only SuperAdmin can access raw materials."},
                status=status.HTTP_403_FORBIDDEN,
            )

        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        return Response({"count": queryset.count(), "results": serializer.data})


class PromoCodeListCreateView(generics.ListCreateAPIView):
    queryset = PromoCode.objects.all()
    serializer_class = PromoCodeSerializer

    def get_queryset(self):
        # user = self.request.user
        user = CustomUser.objects.get(id=1)
        if user.role == "SuperAdmin":
            return PromoCode.objects.all()
        return PromoCode.objects.filter(
            is_active=True,
            valid_from__lte=timezone.now(),
            valid_until__gte=timezone.now(),
        )


class PromoCodeDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PromoCode.objects.all()
    serializer_class = PromoCodeSerializer


class ValidatePromoCodeView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        promo_code = request.data.get("promo_code")
        if not promo_code:
            return Response(
                {"error": "Promo code is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            promo_code_instance = PromoCode.objects.get(
                code=promo_code,
                is_active=True,
                valid_from__lte=timezone.now(),
                valid_until__gte=timezone.now(),
            )
            if (
                promo_code_instance.max_uses
                and promo_code_instance.times_used >= promo_code_instance.max_uses
            ):
                return Response(
                    {"error": "Promo code has reached its maximum usage limit"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response(
                {
                    "valid": True,
                    "code": promo_code_instance.code,
                    "discount_percentage": promo_code_instance.discount_percentage,
                    "message": "Promo code applied successfully",
                }
            )

        except PromoCode.DoesNotExist:
            return Response(
                {"error": "Invalid promo code"}, status=status.HTTP_400_BAD_REQUEST
            )


class OrderDetailUpdateView(generics.RetrieveUpdateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = (JSONParser, FormParser, MultiPartParser)

    def get_queryset(self):
        """Filter orders based on user role"""
        user = self.request.user
        if user.role == "SuperAdmin":
            return Order.objects.filter(factory=user.factory)
        elif user.role == "Distributor":
            return Order.objects.filter(distributor=user.distributor)
        elif user.role in ["Franchise", "SalesPerson", "Packaging"]:
            return Order.objects.filter(franchise=user.franchise)
        elif user.role == "YDM_Logistics":
            return Order.objects.filter(logistics="YDM")

        return Order.objects.none()

    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            old_status = instance.order_status
            comment = request.data.get("comment", None)
            # Create a dictionary only with fields that are actually provided in the request
            modified_data = {}

            # Handle order products separately
            order_products = None

            if "logistics" in request.data:
                modified_data["logistics"] = request.data.get("logistics")

            if "order_status" in request.data:
                modified_data["order_status"] = request.data.get("order_status")

            if modified_data.get("logistics") == "YDM":
                modified_data["order_status"] = "Sent to YDM"

            if (
                modified_data.get("logistics") == "DASH"
                and instance.order_status == "Sent to YDM"
            ):
                modified_data["order_status"] = "Pending"

            if modified_data.get("order_status") == "Sent to YDM":
                modified_data["logistics"] = "YDM"

            if modified_data.get("order_status") == "Sent to Dash":
                modified_data["logistics"] = "DASH"

            # Check if order_products is provided and parse it
            if "order_products" in request.data:
                if isinstance(request.data.get("order_products"), list):
                    order_products = request.data.get("order_products")
                elif hasattr(request.data, "getlist"):
                    order_products_str = request.data.get("order_products")
                    if order_products_str:
                        try:
                            import json

                            order_products = json.loads(order_products_str)
                        except json.JSONDecodeError:
                            return Response(
                                {"error": "Invalid order_products format"},
                                status=status.HTTP_400_BAD_REQUEST,
                            )

            # ----------------------------
            # 2️⃣ Handle free delivery toggle
            # ----------------------------
            if "is_delivery_free" in request.data:
                new_is_delivery_free = str(
                    request.data.get("is_delivery_free")
                ).lower() in ["true", "1", "yes"]

                # Deduct 100 if turned ON
                if new_is_delivery_free and not instance.is_delivery_free:
                    instance.total_amount -= 100

                # Add 100 if turned OFF
                if not new_is_delivery_free and instance.is_delivery_free:
                    instance.total_amount += 100

                modified_data["is_delivery_free"] = new_is_delivery_free
                instance.is_delivery_free = new_is_delivery_free

            # Only include fields that are actually provided in the request
            fields_to_check = [
                "full_name",
                "city",
                "delivery_address",
                "landmark",
                "phone_number",
                "alternate_phone_number",
                "delivery_charge",
                "payment_method",
                "total_amount",
                "promo_code",
                "remarks",
                "dash_location",
                "prepaid_amount",
                "delivery_type",
                "created_at",
                "updated_at",
            ]

            for field in fields_to_check:
                if field in request.data:
                    modified_data[field] = request.data.get(field)

            # Handle payment screenshot if provided
            if "payment_screenshot" in request.FILES:
                modified_data["payment_screenshot"] = request.FILES[
                    "payment_screenshot"
                ]
            elif request.data.get("payment_screenshot"):
                modified_data["payment_screenshot"] = request.data.get(
                    "payment_screenshot"
                )

            # Validate promo code if provided
            if "promo_code" in modified_data:
                promo_code = modified_data["promo_code"]
                try:
                    promo_code_instance = PromoCode.objects.get(
                        code=promo_code,
                        is_active=True,
                        valid_from__lte=timezone.now(),
                        valid_until__gte=timezone.now(),
                    )
                    if (
                        promo_code_instance.max_uses
                        and promo_code_instance.times_used
                        >= promo_code_instance.max_uses
                    ):
                        return Response(
                            {"error": "Promo code has reached its maximum usage limit"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                except PromoCode.DoesNotExist:
                    return Response(
                        {"error": "Invalid promo code"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # If someone tries to update the status, return an error
            if "order_status" in request.data:
                return Response(
                    {"error": "Order status cannot be updated through this endpoint"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Update the instance with only the modified fields
            serializer = self.get_serializer(instance, data=modified_data, partial=True)
            serializer.is_valid(raise_exception=True)
            order = serializer.save()

            new_status = order.order_status
            create_order_log(
                order, old_status, new_status, user=request.user, comment=comment
            )

            # Handle order products if provided
            if order_products is not None:
                # Delete existing order products
                instance.order_products.all().delete()
                # Create new order products
                for product_data in order_products:
                    OrderProduct.objects.create(
                        order=instance,
                        product_id=product_data["product_id"],
                        quantity=product_data["quantity"],
                    )

            # Update promo code usage if changed and provided
            if (
                "promo_code" in modified_data
                and instance.promo_code != promo_code_instance
            ):
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
                status=status.HTTP_400_BAD_REQUEST,
            )


class InventoryCheckView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def _get_low_quantity_items(self, inventory_queryset, critical_threshold=50):
        """Helper method to get low quantity items from inventory queryset"""
        low_quantity_items = []
        for item in inventory_queryset:
            if item.quantity < critical_threshold:
                low_quantity_items.append(
                    {
                        "product_name": item.product.name,
                        "quantity": item.quantity,
                        "status": "critical" if item.quantity <= 25 else "low",
                    }
                )
        return sorted(low_quantity_items, key=lambda x: x["quantity"])

    def _format_inventory_response(self, low_quantity_items):
        """Helper method to format inventory response"""
        return {
            "low_quantity_items": low_quantity_items,
            "total_low_items": len(low_quantity_items),
        }

    def _get_inventory_by_owner(self, owner_type, owner):
        """Helper method to get inventory by owner type"""
        return Inventory.objects.filter(**{owner_type: owner})

    def get(self, request):
        franchise = request.query_params.get("franchise")
        distributor = request.query_params.get("distributor")
        user = self.request.user
        critical_threshold = 50

        try:
            if user.role == "SuperAdmin":
                if franchise:
                    inventory_items = self._get_inventory_by_owner(
                        "franchise", franchise
                    )
                    low_quantity_items = self._get_low_quantity_items(
                        inventory_items, critical_threshold
                    )
                    return Response(self._format_inventory_response(low_quantity_items))
                elif distributor:
                    inventory_items = self._get_inventory_by_owner(
                        "distributor", distributor
                    )
                    low_quantity_items = self._get_low_quantity_items(
                        inventory_items, critical_threshold
                    )
                    return Response(self._format_inventory_response(low_quantity_items))

                response_data = {
                    "factory": {"low_quantity_items": [], "total_low_items": 0},
                    "distributors": {},
                    "franchises": {},
                }

                # Get factory inventory
                factory_inventory = self._get_inventory_by_owner(
                    "factory", user.factory
                )
                factory_low_items = self._get_low_quantity_items(
                    factory_inventory, critical_threshold
                )
                response_data["factory"].update(
                    self._format_inventory_response(factory_low_items)
                )

                # Get distributor inventory
                for dist in Distributor.objects.filter(factory=user.factory):
                    dist_inventory = self._get_inventory_by_owner("distributor", dist)
                    dist_low_items = self._get_low_quantity_items(
                        dist_inventory, critical_threshold
                    )
                    if dist_low_items:
                        response_data["distributors"][dist.name] = (
                            self._format_inventory_response(dist_low_items)
                        )

                # Get franchise inventory
                for fran in Franchise.objects.filter(distributor__factory=user.factory):
                    fran_inventory = self._get_inventory_by_owner("franchise", fran)
                    fran_low_items = self._get_low_quantity_items(
                        fran_inventory, critical_threshold
                    )
                    if fran_low_items:
                        response_data["franchises"][fran.name] = (
                            self._format_inventory_response(fran_low_items)
                        )

                return Response(response_data)

            elif user.role == "Distributor":
                inventory_items = self._get_inventory_by_owner(
                    "distributor", user.distributor
                )
                low_quantity_items = self._get_low_quantity_items(
                    inventory_items, critical_threshold
                )
                return Response(self._format_inventory_response(low_quantity_items))

            elif user.role in ["Franchise", "SalesPerson", "Packaging"]:
                inventory_items = self._get_inventory_by_owner(
                    "franchise", user.franchise
                )
                low_quantity_items = self._get_low_quantity_items(
                    inventory_items, critical_threshold
                )
                return Response(self._format_inventory_response(low_quantity_items))

            else:
                return Response(
                    {"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN
                )

        except Exception as e:
            return Response(
                {"error": f"Failed to check inventory: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class SearchInJSONFieldFilter(DjangoFilterBackend):
    def filter_queryset(self, request, queryset, view):
        search_query = request.query_params.get("search", "").strip().lower()
        if not search_query:
            return queryset

        filtered_queryset = []

        for location in queryset:
            match_in_name = search_query in location.name.lower()
            match_in_coverage = any(
                search_query in area.lower() for area in location.coverage_areas
            )

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
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"error": "No file provided"}, status=400)

        filename = uploaded_file.name.lower()

        try:
            # Initialize storage for parsed rows
            rows = []
            if filename.endswith(".xlsx"):
                # Read Excel file in-memory
                wb = openpyxl.load_workbook(uploaded_file, read_only=True)
                sheet = wb.active
                headers = [cell.value for cell in sheet[1]]

                loc_idx = headers.index("Location Name")
                area_idx = headers.index("Coverage Area")

                for row in sheet.iter_rows(min_row=2, values_only=True):
                    rows.append([row[loc_idx], row[area_idx]])

            elif filename.endswith(".csv"):
                # Read CSV file in-memory
                decoded_file = uploaded_file.read().decode("utf-8")
                io_string = io.StringIO(decoded_file)
                reader = csv.reader(io_string)
                headers = next(reader)

                loc_idx = headers.index("Location Name")
                area_idx = headers.index("Coverage Area")

                for row in reader:
                    rows.append([row[loc_idx], row[area_idx]])

            else:
                return Response(
                    {"error": "Unsupported file type. Use .xlsx or .csv"}, status=400
                )

        except Exception as e:
            return Response({"error": f"Failed to process file: {str(e)}"}, status=400)

        # Save to DB
        created, updated = 0, 0
        for location_name, coverage_raw in rows:
            if not location_name or not coverage_raw:
                continue

            location_name = str(location_name).strip()
            coverage_list = [
                area.strip() for area in str(coverage_raw).split(",") if area.strip()
            ]

            location, is_created = Location.objects.get_or_create(name=location_name)

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

        return Response(
            {
                "message": "Upload successful",
                "locations_created": created,
                "locations_updated": updated,
            },
            status=201,
        )


@csrf_exempt
def switch_db(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    demo = data.get("demo_data", None)
    print("demo", demo)
    if demo is None:
        return JsonResponse(
            {"error": 'Missing "demo_data" key in request body'}, status=400
        )
    if isinstance(demo, str):
        demo = demo.lower() == "true"
    print("demo", demo)

    if not isinstance(demo, bool):
        return JsonResponse(
            {"error": '"demo_data" must be a boolean (true or false)'}, status=400
        )

    try:
        # Set demo_data in both databases as per your logic
        main_config = DatabaseMode.objects.using("default").get_or_create(pk=1)[0]
        demo_config = DatabaseMode.objects.using("demo").get_or_create(pk=1)[0]

        if demo:
            main_config.demo_data = False
            demo_config.demo_data = True
            main_config.save(using="default")
            demo_config.save(using="demo")
            set_current_db_name(True)  # Switch to demo
            current_mode = "demo"
        else:
            main_config.demo_data = False
            demo_config.demo_data = True
            main_config.save(using="default")
            demo_config.save(using="demo")
            set_current_db_name(False)  # Switch to main
            current_mode = "main"

        return JsonResponse(
            {
                "message": f"Switched to {current_mode} database",
                "current_mode": current_mode,
                "success": True,
            },
            status=200,
        )

    except Exception as e:
        return JsonResponse(
            {"error": f"Failed to switch database: {str(e)}"}, status=500
        )


@method_decorator(csrf_exempt, name="dispatch")
class CurrentDatabaseModeView(APIView):
    """
    Returns which database is currently active.
    Response: { "is_demodatabase": true/false }
    """

    def get(self, request):
        try:
            # Use your middleware's getter to check which DB is active
            is_demo = get_current_db_name() == "demo"
            return Response({"is_demodatabase": is_demo})
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class InventoryDateSnapshotView(generics.GenericAPIView):
    """
    Get inventory snapshot at end of a specific date

    Usage Examples:
    - GET /api/inventory-date-snapshot/?date=2024-01-15
    - GET /api/inventory-date-snapshot/?date=2024-01-15&product_id=1
    - GET /api/inventory-date-snapshot/?date=2024-01-15&status=ready_to_dispatch

    Returns: All inventory items with their quantities as they were at the end of the specified date
    """

    permission_classes = [IsAuthenticated]
    serializer_class = InventorySnapshotSerializer

    def get(self, request, *args, **kwargs):
        # Get query parameters
        date_param = request.query_params.get("date")
        product_id = request.query_params.get("product_id")
        inventory_status = request.query_params.get("status")

        if not date_param:
            return Response(
                {
                    "error": "Date parameter is required. Format: YYYY-MM-DD",
                    "example": "GET /api/inventory-date-snapshot/?date=2024-01-15",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Parse the date
        try:
            target_date = parse_date(date_param)
            if not target_date:
                # Try parsing as datetime and extract date
                target_datetime = parse_datetime(date_param)
                if target_datetime:
                    target_date = target_datetime.date()
                else:
                    raise ValueError("Invalid date format")
        except (ValueError, TypeError):
            return Response(
                {
                    "error": "Invalid date format. Use YYYY-MM-DD",
                    "examples": ["2024-01-15", "2024-12-31"],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Set end of day for the target date (23:59:59)
        end_of_day = datetime.combine(target_date, time.max)

        user = request.user
        snapshot_data = []

        # Build role-based inventory filter
        try:
            inventory_queryset = self._get_user_inventories(
                user, end_of_day, product_id, inventory_status
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)

        # Process each inventory item
        for inventory in inventory_queryset:
            snapshot_item = self._get_inventory_snapshot_item(inventory, end_of_day)
            if snapshot_item:
                snapshot_data.append(snapshot_item)

        # Sort by product name for consistency
        snapshot_data.sort(key=lambda x: x["product_name"])

        return Response({"results": snapshot_data})

    def _get_user_inventories(
        self, user, end_of_day, product_id=None, inventory_status=None
    ):
        """Get inventories based on user role and filters"""

        # Base filter - only inventories that existed by the target date
        base_filter = Q(created_at__lte=end_of_day)

        # Apply role-based filtering
        if not hasattr(user, "role"):
            raise ValueError("User role not found")

        if user.role == "SuperAdmin":
            if hasattr(user, "factory"):
                base_filter &= Q(factory=user.factory)
            else:
                raise ValueError("SuperAdmin user must have factory assigned")

        elif user.role == "Distributor":
            if hasattr(user, "distributor"):
                base_filter &= Q(distributor=user.distributor)
            else:
                raise ValueError("Distributor user must have distributor assigned")

        elif user.role == "Franchise":
            if hasattr(user, "franchise"):
                base_filter &= Q(franchise=user.franchise)
            else:
                raise ValueError("Franchise user must have franchise assigned")

        elif user.role == "SalesPerson":
            # For sales person, get inventories they have interacted with
            inventory_ids = (
                InventoryChangeLog.objects.filter(user=user, changed_at__lte=end_of_day)
                .values_list("inventory_id", flat=True)
                .distinct()
            )
            base_filter &= Q(id__in=inventory_ids)
        else:
            raise ValueError(f"Invalid user role: {user.role}")

        # Apply additional filters
        if product_id:
            base_filter &= Q(product_id=product_id)
        if inventory_status:
            base_filter &= Q(status=inventory_status)

        return Inventory.objects.filter(base_filter).select_related(
            "product", "factory", "distributor", "franchise"
        )

    def _get_inventory_snapshot_item(self, inventory, end_of_day):
        """Get snapshot data for a single inventory item"""

        # Get the latest change log for this inventory up to the target date
        latest_log = (
            InventoryChangeLog.objects.filter(
                inventory=inventory, changed_at__lte=end_of_day
            )
            .order_by("-changed_at")
            .first()
        )

        if latest_log:
            # Use quantity from the latest log
            current_quantity = latest_log.new_quantity
        else:
            # If no change logs exist up to this date, check if inventory existed
            if inventory.created_at <= end_of_day:
                # Use the original quantity from inventory
                current_quantity = inventory.quantity
            else:
                # Skip this inventory as it didn't exist at the target date
                return None

        return {
            "inventory_id": inventory.id,
            "product_id": inventory.product.id,
            "product_name": inventory.product.name,
            "quantity": current_quantity,
        }

    def _get_location_info(self, inventory):
        """Get location type and name for inventory"""
        if inventory.factory:
            return "Factory", str(inventory.factory)
        elif inventory.distributor:
            return "Distributor", str(inventory.distributor)
        elif inventory.franchise:
            return "Franchise", str(inventory.franchise)
        else:
            return "Unknown", "No Location Set"
