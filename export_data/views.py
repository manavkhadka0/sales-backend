import csv
from datetime import datetime

from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from django_filters import rest_framework as django_filters
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from account.models import CustomUser, Franchise
from sales.models import Order, OrderProduct

# Create your views here.


class OrderCSVExportView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get orders based on user role
        user = request.user
        logistics = request.query_params.get("logistics")

        if user.role == "SuperAdmin":
            orders = Order.objects.filter(factory=user.factory)
        elif user.role == "Distributor":
            franchises = Franchise.objects.filter(distributor=user.distributor)
            orders = Order.objects.filter(franchise__in=franchises)
        elif user.role == "Franchise":
            orders = Order.objects.filter(
                franchise=user.franchise, order_status="Processing"
            ).order_by("-id")
        elif user.role == "Packaging":
            orders = Order.objects.filter(
                franchise=user.franchise, order_status="Processing"
            ).order_by("-id")
        else:
            return Response(
                {"error": "Unauthorized to export orders"},
                status=status.HTTP_403_FORBIDDEN,
            )
        if logistics:
            orders = orders.filter(logistics=logistics)

        if not orders.exists():
            return Response(
                {"error": "No orders found to export"}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            # Create the HttpResponse object with CSV header
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="orders.csv"'

            # Create CSV writer
            writer = csv.writer(response)

            # Write header row with new fields
            writer.writerow(
                [
                    "Customer Name",
                    "Contact Number",
                    "Alternative Number",
                    "Location",
                    "Customer Landmark",
                    "Address",
                    "Customer Order ID",
                    "Product Name",
                    "Product Price",
                    "Payment Type",
                    "Client Note",
                ]
            )

            # Write data rows
            for order in orders:
                # Format products string as requested
                products = OrderProduct.objects.filter(order=order)
                products_str = ",".join(
                    [f"{p.quantity}-{p.product.product.name}" for p in products]
                )

                # Calculate product price
                product_price = order.total_amount
                if order.prepaid_amount:
                    product_price = order.total_amount - order.prepaid_amount

                # Determine payment type
                payment_type = (
                    "pre-paid"
                    if order.prepaid_amount
                    and (order.total_amount - order.prepaid_amount) == 0
                    else "cashOnDelivery"
                )
                address_parts = []
                if getattr(order, "delivery_address", None):
                    address_parts.append(order.delivery_address)
                if getattr(order, "city", None):
                    address_parts.append(order.city)
                full_address = ", ".join(address_parts)

                writer.writerow(
                    [
                        order.full_name,  # Customer Name
                        order.phone_number,  # Contact Number
                        order.alternate_phone_number or "",  # Alternative Number
                        order.dash_location.name if order.dash_location else "",
                        "",
                        full_address,  # Address
                        "",
                        products_str,  # Product Name
                        product_price,  # Product Price
                        payment_type,  # Payment Type
                        order.remarks or "",  # Client Note
                    ]
                )

            # After successful export, update all processed orders to "Sent to Dash"
            orders.update(order_status="Sent to Dash")

            return response

        except Exception as e:
            return Response(
                {"error": f"Failed to export orders: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SalesPersonOrderCSVExportView(generics.GenericAPIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request, phone_number):
        excluded_statuses = [
            "Cancelled",
            "Returned By Customer",
            "Returned By Dash",
            "Return Pending",
        ]

        # Get date range from query parameters
        start_date = request.query_params.get("date")
        end_date = request.query_params.get("end_date")

        if not start_date or not end_date:
            return Response(
                {"error": "Both start_date and end_date are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Convert string dates to datetime objects
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get sales person by phone number
        try:
            salesperson = CustomUser.objects.get(
                phone_number=phone_number, role="SalesPerson"
            )
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "Sales person not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Get orders for the sales person within date range
        orders = Order.objects.filter(
            sales_person=salesperson,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
        ).order_by("-id")

        if not orders.exists():
            return Response(
                {"error": "No orders found to export"}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            # Create the HttpResponse object with CSV header
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="orders.csv"'

            # Create CSV writer
            writer = csv.writer(response)

            # Write header row with new fields
            writer.writerow(
                [
                    "Date",
                    "Customer Name",
                    "Contact Number",
                    "Alternative Number",
                    "Address",
                    "Product Name",
                    "Product Price",
                    "Payment Type",
                    "Order Status",
                    "Remarks",
                ]
            )

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
                products_str = ",".join(
                    [f"{p.quantity}-{p.product.product.name}" for p in products]
                )

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

                writer.writerow(
                    [
                        order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        order.full_name,  # Customer Name
                        order.phone_number,  # Contact Number
                        order.alternate_phone_number or "",  # Alternative Number
                        order.delivery_address,  # Address
                        products_str,  # Product Name
                        # Product Price
                        f"{product_price}",
                        order.payment_method
                        +
                        # Payment Type
                        (f" ({order.prepaid_amount})" if order.prepaid_amount else ""),
                        order.order_status,
                        order.remarks or "",  # Client Note
                    ]
                )

            # Add summary statistics
            writer.writerow([])  # Empty row for spacing
            writer.writerow(["Summary Statistics"])
            writer.writerow(["Overall Orders", overall_orders])
            writer.writerow(["Overall Amount", overall_amount])
            writer.writerow(["Total Orders", total_orders])
            writer.writerow(["Total Amount", total_amount])
            writer.writerow(["Total Cancelled Orders", total_cancelled_orders])
            writer.writerow(["Total Cancelled Amount", total_cancelled_amount])

            return response

        except Exception as e:
            return Response(
                {"error": f"Failed to export orders: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SalesSummaryExportView(APIView):
    """
    Exports sales summary for a given date range.
    Query params: start_date, end_date (YYYY-MM-DD)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        if not start_date or not end_date:
            return Response(
                {"error": "start_date and end_date are required in YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Define cancelled statuses
        cancelled_statuses = [
            "Cancelled",
            "Returned By Customer",
            "Returned By Dash",
            "Return Pending",
        ]

        # Filter orders in date range

        orders = Order.objects.filter(
            created_at__date__gte=start_date_obj, created_at__date__lte=end_date_obj
        )
        if (
            hasattr(user, "role")
            and user.role == "Franchise"
            and hasattr(user, "franchise")
            and user.franchise
        ):
            orders = orders.filter(franchise=user.franchise)

        # Total orders and amount (do NOT exclude cancelled)
        total_orders = orders.count()
        total_amount = orders.aggregate(total=Sum("total_amount"))["total"] or 0

        # Cancelled orders and amount
        total_cancelled_orders = orders.filter(
            order_status__in=cancelled_statuses
        ).count()
        total_cancelled_amount = (
            orders.filter(order_status__in=cancelled_statuses).aggregate(
                total=Sum("total_amount")
            )["total"]
            or 0
        )

        # Gross orders/amount
        gross_orders = total_orders - total_cancelled_orders
        gross_amount = float(total_amount) - float(total_cancelled_amount)

        # Product-wise sales (non-cancelled)
        product_sales = (
            OrderProduct.objects.filter(
                order__in=orders.exclude(order_status__in=cancelled_statuses)
            )
            .values("product__product__id", "product__product__name")
            .annotate(quantity_sold=Sum("quantity"))
            .order_by("-quantity_sold")
        )

        # Product-wise cancelled sales
        cancelled_product_sales = (
            OrderProduct.objects.filter(
                order__in=orders.filter(order_status__in=cancelled_statuses)
            )
            .values("product__product__id", "product__product__name")
            .annotate(quantity_cancelled=Sum("quantity"))
            .order_by("-quantity_cancelled")
        )

        try:
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = (
                f'attachment; filename="sales_summary_{start_date}_to_{end_date}.csv"'
            )
            writer = csv.writer(response)

            writer.writerow(["SALES SUMMARY REPORT"])
            writer.writerow([f"Date Range: {start_date} to {end_date}"])
            writer.writerow(
                [f"Generated On: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"]
            )
            writer.writerow([])

            # Report Title and Date Range
            # 1. Write Order Data Table
            writer.writerow(["ORDER DETAILS"])
            writer.writerow(
                [
                    "Date",
                    "Customer Name",
                    "Contact Number",
                    "Alternative Number",
                    "Location",
                    "Customer Landmark",
                    "Address",
                    "Customer Order ID",
                    "Product Name",
                    "Product Price",
                    "Payment Type",
                    "Order Status",
                    "Client Note",
                ]
            )

            for order in orders:
                products = OrderProduct.objects.filter(order=order)
                products_str = ", ".join(
                    [f"{p.quantity}-{p.product.product.name}" for p in products]
                )
                product_price = order.total_amount
                payment_type = (
                    "pre-paid"
                    if order.prepaid_amount
                    and (order.total_amount - order.prepaid_amount) == 0
                    else "cashOnDelivery"
                )
                address_parts = []
                if getattr(order, "delivery_address", None):
                    address_parts.append(order.delivery_address)
                if getattr(order, "city", None):
                    address_parts.append(order.city)
                full_address = ", ".join(address_parts)

                writer.writerow(
                    [
                        order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        order.full_name,
                        order.phone_number,
                        order.alternate_phone_number or "",
                        order.dash_location.name
                        if getattr(order, "dash_location", None)
                        else "",
                        getattr(order, "landmark", ""),
                        full_address,
                        "",
                        products_str,
                        product_price,
                        payment_type,
                        order.order_status,
                        order.remarks or "",
                    ]
                )

            # 2. Blank row before summary
            writer.writerow([])

            # Summary Metrics Section
            writer.writerow(["SUMMARY METRICS"])
            writer.writerow(["Metric", "Value"])
            summary_rows = [
                ("Total Orders", total_orders),
                ("Total Cancelled Orders", total_cancelled_orders),
                ("Gross Orders", gross_orders),
                ("Total Amount", float(total_amount)),
                ("Total Cancelled Amount", float(total_cancelled_amount)),
                ("Gross Amount", gross_amount),
            ]
            for metric, value in summary_rows:
                writer.writerow([metric, value])
            writer.writerow([])  # Blank row after summary

            # Product Sold Table
            writer.writerow(["PRODUCTS SOLD"])
            writer.writerow(["Product Name", "Quantity Sold"])
            for p in product_sales:
                writer.writerow([p["product__product__name"], p["quantity_sold"]])
            if not product_sales:
                writer.writerow(["-", 0])
            writer.writerow([])  # Blank row

            # Product Cancelled Table
            writer.writerow(["PRODUCTS CANCELLED"])
            writer.writerow(["Product Name", "Quantity Cancelled"])
            for p in cancelled_product_sales:
                writer.writerow([p["product__product__name"], p["quantity_cancelled"]])
            if not cancelled_product_sales:
                writer.writerow(["-", 0])
            writer.writerow([])  # Final blank row

            return response
        except Exception as e:
            return Response(
                {"error": f"Failed to export sales summary: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PackagingSentToDashSummaryCSVView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if getattr(user, "role", None) != "Packaging":
            return Response(
                {"error": "Only Packaging role can access this endpoint."}, status=403
            )

        date_str = request.query_params.get("date")
        if not date_str:
            return Response(
                {"error": "date is required in YYYY-MM-DD format."}, status=400
            )

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD."}, status=400
            )

        orders = Order.objects.filter(
            franchise=user.franchise,
            order_status="Sent to Dash",
            created_at__date=date_obj,
        )

        total_amount = orders.aggregate(total=Sum("total_amount"))["total"] or 0
        total_orders = orders.count()

        product_sales = (
            OrderProduct.objects.filter(order__in=orders)
            .values("product__product__name")
            .annotate(quantity_sold=Sum("quantity"))
            .order_by("-quantity_sold")
        )

        # Prepare CSV response
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="packaging_sent_to_dash_summary_{date_str}.csv"'
        )
        writer = csv.writer(response)
        writer.writerow(["Date", date_str])
        writer.writerow([])

        # Write summary section
        writer.writerow(["Total Amount", float(total_amount)])
        writer.writerow(["Total Orders", total_orders])
        writer.writerow([])  # Blank row

        # 1. Write Order Data Table
        writer.writerow(["ORDER DETAILS"])
        writer.writerow(
            [
                "Date",
                "Customer Name",
                "Contact Number",
                "Alternative Number",
                "Location",
                "Customer Landmark",
                "Address",
                "Product Name",
                "Product Price",
                "Payment Type",
                "Order Status",
                "Dash Delivery Charge",
            ]
        )

        for order in orders:
            products = OrderProduct.objects.filter(order=order)
            products_str = ", ".join(
                [f"{p.quantity}-{p.product.product.name}" for p in products]
            )
            product_price = order.total_amount
            payment_type = (
                "pre-paid"
                if order.prepaid_amount
                and (order.total_amount - order.prepaid_amount) == 0
                else "cashOnDelivery"
            )
            address_parts = []
            if getattr(order, "delivery_address", None):
                address_parts.append(order.delivery_address)
            if getattr(order, "city", None):
                address_parts.append(order.city)
            full_address = ", ".join(address_parts)

            writer.writerow(
                [
                    order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    order.full_name,
                    order.phone_number,
                    order.alternate_phone_number or "",
                    order.dash_location.name
                    if getattr(order, "dash_location", None)
                    else "",
                    getattr(order, "landmark", ""),
                    full_address,
                    products_str,
                    product_price,
                    payment_type,
                    order.order_status,
                    "",
                ]
            )

        # 2. Blank row before summary
        writer.writerow([])

        # Write product breakdown section
        product_names = [p["product__product__name"] for p in product_sales]
        quantities = [p["quantity_sold"] for p in product_sales]

        if product_names:
            writer.writerow(product_names)
            writer.writerow(quantities)
        else:
            writer.writerow(["No Products"])
            writer.writerow(["0"])

        return response


class CustomOrderFilter(django_filters.FilterSet):
    """Filtered Order API with specific filters"""

    # Date range filters
    date_from = django_filters.DateFilter(
        field_name="created_at__date",
        lookup_expr="gte",
        help_text="Filter orders from this date (YYYY-MM-DD)",
    )
    date_to = django_filters.DateFilter(
        field_name="created_at__date",
        lookup_expr="lte",
        help_text="Filter orders up to this date (YYYY-MM-DD)",
    )

    # Order date range filters
    order_date_from = django_filters.DateFilter(
        field_name="date",
        lookup_expr="gte",
        help_text="Filter by order date from (YYYY-MM-DD)",
    )
    order_date_to = django_filters.DateFilter(
        field_name="date",
        lookup_expr="lte",
        help_text="Filter by order date up to (YYYY-MM-DD)",
    )

    # Franchise filter
    franchise = django_filters.ModelChoiceFilter(
        queryset=Franchise.objects.all(), help_text="Filter by franchise ID"
    )

    # Total amount range filters
    total_amount_min = django_filters.NumberFilter(
        field_name="total_amount", lookup_expr="gte", help_text="Minimum total amount"
    )
    total_amount_max = django_filters.NumberFilter(
        field_name="total_amount", lookup_expr="lte", help_text="Maximum total amount"
    )

    # Product count range filters
    products_count_min = django_filters.NumberFilter(
        method="filter_products_count_min",
        help_text="Minimum number of products in order",
    )
    products_count_max = django_filters.NumberFilter(
        method="filter_products_count_max",
        help_text="Maximum number of products in order",
    )

    # More than 3 products filter
    more_than_3_products = django_filters.BooleanFilter(
        method="filter_more_than_3_products",
        help_text="Filter orders with more than 3 products (true/false)",
    )

    # Multiple orders by same customer
    multiple_orders_customer = django_filters.BooleanFilter(
        method="filter_multiple_orders_customer",
        help_text="Filter customers with multiple orders (true/false)",
    )

    oil_bottle_total_min = django_filters.NumberFilter(
        method="filter_oil_bottle_total_min",
        help_text='Minimum total quantity of items with name containing "oil bottle"',
    )
    oil_bottle_only = django_filters.BooleanFilter(
        method="filter_oil_bottle_only",
        help_text='Filter orders containing only items with name containing "oil bottle" (true/false)',
    )

    class Meta:
        model = Order
        fields = []

    def filter_products_count_min(self, queryset, name, value):
        """Filter orders with minimum number of products"""
        if value is not None:
            return queryset.annotate(products_count=Count("order_products")).filter(
                products_count__gte=value
            )
        return queryset

    def filter_products_count_max(self, queryset, name, value):
        """Filter orders with maximum number of products"""
        if value is not None:
            return queryset.annotate(products_count=Count("order_products")).filter(
                products_count__lte=value
            )
        return queryset

    def filter_more_than_3_products(self, queryset, name, value):
        if value:
            # Simple approach: get orders where total quantity > 3
            order_ids = []
            for order in queryset:
                total_qty = sum(op.quantity for op in order.order_products.all())
                max_qty = (
                    max(op.quantity for op in order.order_products.all())
                    if order.order_products.exists()
                    else 0
                )

                if max_qty >= 3 or total_qty >= 3:
                    order_ids.append(order.id)

            return queryset.filter(id__in=order_ids)
        return queryset

    def filter_multiple_orders_customer(self, queryset, name, value):
        """Filter customers with multiple orders"""
        if value:
            # Get customers with multiple orders
            customers_with_multiple = (
                Order.objects.values("phone_number")
                .annotate(order_count=Count("id"))
                .filter(order_count__gt=1)
                .values_list("phone_number", flat=True)
            )
            return queryset.filter(phone_number__in=customers_with_multiple)
        return queryset

    def filter_oil_bottle_total_min(self, queryset, name, value):
        """Filter orders where total quantity of items with name containing 'oil bottle' is >= value"""
        if value is not None:
            annotated = queryset.annotate(
                oil_bottle_qty=Sum(
                    "order_products__quantity",
                    filter=Q(
                        order_products__product__product__name__icontains="oil bottle"
                    ),
                )
            )
            return annotated.filter(oil_bottle_qty__gte=value)
        return queryset

    def filter_oil_bottle_only(self, queryset, name, value):
        """If true, return orders that contain only items whose name contains 'oil bottle'."""
        if value:
            annotated = queryset.annotate(
                non_oil_item_count=Count(
                    "order_products",
                    filter=~Q(
                        order_products__product__product__name__icontains="oil bottle"
                    ),
                ),
                oil_bottle_qty=Sum(
                    "order_products__quantity",
                    filter=Q(
                        order_products__product__product__name__icontains="oil bottle"
                    ),
                ),
            )
            # Only oil-bottle items and at least one such item
            return annotated.filter(non_oil_item_count=0, oil_bottle_qty__gt=0)
        return queryset


@api_view(["GET"])
def export_orders_csv_api(request):
    """
    Export filtered orders to CSV file (similar to SalesPersonOrderCSVExportView)

    Same filters as OrderListAPIView apply here
    """
    import csv

    # Get base queryset
    queryset = Order.objects.select_related(
        "franchise",
        "distributor",
        "factory",
        "sales_person",
        "dash_location",
        "promo_code",
    ).prefetch_related("order_products__product__product")

    # Annotate with products count
    queryset = queryset.annotate(products_count=Count("order_products"))

    # Apply filters
    order_filter = CustomOrderFilter(request.GET, queryset=queryset)
    filtered_orders = order_filter.qs.order_by("-id")

    if not filtered_orders.exists():
        return Response(
            {"error": "No orders found to export"}, status=status.HTTP_404_NOT_FOUND
        )

    # Limit export to prevent memory issues
    max_export_limit = 10000
    if filtered_orders.count() > max_export_limit:
        return Response(
            {
                "error": f"Too many records to export. Limit is {max_export_limit} records."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # Create CSV response
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="filtered_orders_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        )

        # Create CSV writer
        writer = csv.writer(response)

        # Write header row matching the existing format
        writer.writerow(
            [
                "Date",
                "Customer Name",
                "Contact Number",
                "Alternative Number",
                "Address",
                "Product Name",
                "Product Price",
                "Payment Type",
                "Order Status",
                "Remarks",
            ]
        )

        # Excluded statuses for summary calculations
        excluded_statuses = [
            "Cancelled",
            "Returned By Customer",
            "Returned By Dash",
            "Return Pending",
        ]

        # Initialize summary variables
        total_orders = 0
        total_amount = 0
        total_cancelled_orders = 0
        total_cancelled_amount = 0
        overall_orders = 0
        overall_amount = 0

        # Write data rows
        for order in filtered_orders:
            # Format products string as in existing code
            products = OrderProduct.objects.filter(order=order)
            products_str = ",".join(
                [f"{p.quantity}-{p.product.product.name}" for p in products]
            )

            # Calculate product price
            product_price = float(order.total_amount)

            overall_orders += 1
            overall_amount += product_price

            # Update summary statistics
            if order.order_status not in excluded_statuses:
                total_orders += 1
                total_amount += product_price

            if order.order_status in excluded_statuses:
                total_cancelled_orders += 1
                total_cancelled_amount += product_price

            # Format payment type with prepaid amount if exists
            payment_type = order.payment_method
            if order.prepaid_amount:
                payment_type += f" ({order.prepaid_amount})"

            writer.writerow(
                [
                    order.created_at.strftime("%Y-%m-%d %H:%M:%S"),  # Date
                    order.full_name,  # Customer Name
                    order.phone_number,  # Contact Number
                    order.alternate_phone_number or "",  # Alternative Number
                    order.delivery_address,  # Address
                    products_str,  # Product Name
                    f"{product_price}",  # Product Price
                    payment_type,  # Payment Type
                    order.order_status,  # Order Status
                    order.remarks or "",  # Remarks
                ]
            )

        # Add summary statistics at the end
        writer.writerow([])  # Empty row for spacing
        writer.writerow(["Summary Statistics"])
        writer.writerow(["Overall Orders", overall_orders])
        writer.writerow(["Overall Amount", f"{overall_amount:.2f}"])
        writer.writerow(["Total Orders", total_orders])
        writer.writerow(["Total Amount", f"{total_amount:.2f}"])
        writer.writerow(["Total Cancelled Orders", total_cancelled_orders])
        writer.writerow(["Total Cancelled Amount", f"{total_cancelled_amount:.2f}"])

        # Add applied filters information
        writer.writerow([])  # Empty row
        writer.writerow(["Applied Filters"])
        for key, value in request.GET.items():
            if value and key != "export":
                writer.writerow([key.replace("_", " ").title(), value])

        return response

    except Exception as e:
        return Response(
            {"error": f"Failed to export orders: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
