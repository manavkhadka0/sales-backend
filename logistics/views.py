# views.py
import csv
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Min, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters import rest_framework as django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.filters import SearchFilter
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from account.models import CustomUser, Franchise
from account.serializers import SmallUserSerializer
from sales.models import OrderProduct

# You'll need to create this serializer
from sales.serializers import OrderSerializer

from .models import (
    AssignOrder,
    FranchisePaymentLog,
    Order,
    OrderChangeLog,
    OrderComment,
)
from .serializers import (
    AssignOrderSerializer,
    FranchisePaymentLogSerializer,
    OrderChangeLogSerializer,
    OrderCommentDetailSerializer,
    OrderCommentSerializer,
)

DELIVERY_CHARGE = 100
CANCELLED_CHARGE = 0


class GetYDMRiderView(generics.ListAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = SmallUserSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = ["first_name", "phone_number", "address"]

    def get_queryset(self):
        return CustomUser.objects.filter(role="YDM_Rider")


class OrderCommentListCreateView(generics.ListCreateAPIView):
    queryset = OrderComment.objects.all()
    serializer_class = OrderCommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


class OrderCommentRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = OrderComment.objects.all()
    serializer_class = OrderCommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


@api_view(["GET"])
@permission_classes([AllowAny])
def track_order(request):
    order_code = request.query_params.get("order_code")
    order = get_object_or_404(Order, order_code=order_code)
    serializer = OrderSerializer(order)
    order_change_log = OrderChangeLogSerializer(order.change_logs.all(), many=True)
    order_comment = OrderCommentDetailSerializer(order.comments.all(), many=True)

    return Response(
        {
            "order": serializer.data,
            "order_change_log": order_change_log.data,
            "order_comment": order_comment.data,
        }
    )


@api_view(["GET"])
def get_franchise_order_stats(request, franchise_id):
    """
    Get order statistics for a franchise where logistics is YDM
    """
    try:
        # Base queryset
        orders = Order.objects.filter(
            franchise_id=franchise_id, logistics="YDM"
        ).exclude(
            order_status__in=[
                "Pending",
                "Processing",
                "Sent to Dash",
                "Indrive",
                "Return By Dash",
            ]
        )

        # Helper function to get stats
        def get_status_stats(statuses):
            if isinstance(statuses, str):
                statuses = [statuses]
            filtered = orders.filter(order_status__in=statuses)
            result = filtered.aggregate(
                count=Count("id"),
                total=Sum("total_amount"),
                prepaid=Sum("prepaid_amount"),
            )
            total = float(result["total"] or 0)
            prepaid = float(result["prepaid"] or 0)
            return {"nos": result["count"] or 0, "amount": total - prepaid}

        # Calculate statistics
        data = {
            "Total Orders": get_status_stats(
                [
                    "Sent to YDM",
                    "Verified",
                    "Out For Delivery",
                    "Rescheduled",
                    "Delivered",
                    "Cancelled",
                    "Returned By Customer",
                    "Returned By YDM",
                    "Return Pending",
                ]
            ),
            "order_processing": {
                "Order Placed": get_status_stats("Sent to YDM"),
                "Order Verified": get_status_stats("Verified"),
            },
            "order_dispatched": {
                "Out For Delivery": get_status_stats("Out For Delivery"),
                "Rescheduled": get_status_stats("Rescheduled"),
            },
            "order_status": {
                "Delivered": get_status_stats("Delivered"),
                "Cancelled": get_status_stats("Returned By YDM"),
                "Pending RTV": get_status_stats("Return Pending"),
            },
        }

        return Response({"success": True, "data": data}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"success": False, "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
def get_complete_dashboard_stats(request, franchise_id):
    """
    Get all dashboard statistics in a single function
    """
    try:
        today = timezone.now().date()
        exclude_status = [
            "Pending",
            "Processing",
            "Sent to Dash",
            "Indrive",
            "Return By Dash",
        ]

        # Base queryset - filter by user's organization
        orders = Order.objects.filter(
            franchise_id=franchise_id, logistics="YDM"
        ).exclude(order_status__in=exclude_status)

        # Helper function to get stats
        def get_status_stats(statuses):
            if isinstance(statuses, str):
                statuses = [statuses]
            filtered = orders.filter(logistics="YDM", order_status__in=statuses)
            result = filtered.aggregate(
                count=Count("id"),
                total=Sum("total_amount"),
                prepaid=Sum("prepaid_amount"),
            )
            total = float(result["total"] or 0)
            prepaid = float(result["prepaid"] or 0)
            return {"nos": result["count"] or 0, "amount": total - prepaid}

        valid_orders = (
            Order.objects.filter(franchise_id=franchise_id, logistics="YDM")
            .filter(order_status="Delivered")
            .count()
        )

        cancelled_orders = Order.objects.filter(
            franchise_id=franchise_id,
            logistics="YDM",
            order_status__in=[
                "Cancelled",
                "Return Pending",
                "Returned By Customer",
                "Returned By YDM",
            ],
        ).count()

        # Calculate total charges
        valid_charge = valid_orders * DELIVERY_CHARGE
        cancelled_charge = cancelled_orders * CANCELLED_CHARGE
        total_charge = valid_charge + cancelled_charge

        # Calculate delivery performance percentages
        completed_orders = orders.filter(
            order_status__in=["Delivered", "Returned By YDM"]
        ).count()
        delivered_count = orders.filter(order_status="Delivered").count()
        cancelled_count = orders.filter(order_status="Returned By YDM").count()

        delivered_percentage = (
            round((delivered_count / completed_orders) * 100, 2)
            if completed_orders > 0
            else 0
        )
        cancelled_percentage = (
            round((cancelled_count / completed_orders) * 100, 2)
            if completed_orders > 0
            else 0
        )

        def get_todays_orders_by_status(status):
            """
            Helper function to get count of orders with specific status(es) change today.
            Only counts the first status change for each order to avoid duplicates.

            Args:
                status: A single status string or a list/tuple of status strings

            Returns:
                int: Count of unique orders with status change matching the criteria
            """
            # First, get the first status change for each order today
            from django.db.models import Min

            # Get the minimum changed_at for each order with the given status(es)
            order_changes = OrderChangeLog.objects.filter(
                changed_at__date=today,
                order__franchise_id=franchise_id,
                order__logistics="YDM",
            )

            if isinstance(status, (list, tuple)):
                order_changes = order_changes.filter(new_status__in=status)
            else:
                order_changes = order_changes.filter(new_status=status)

            # Get the first change log for each order
            first_changes = (
                order_changes.values("order_id")
                .annotate(first_change=Min("id"))
                .values_list("first_change", flat=True)
            )

            # Count the number of unique orders with the first status change matching our criteria
            return len(first_changes)

        # Get today's order counts by status
        todays_orders_count = get_todays_orders_by_status("Sent to YDM")
        todays_deliveries_count = get_todays_orders_by_status("Delivered")
        todays_rescheduled_count = get_todays_orders_by_status("Rescheduled")
        todays_cancellations_count = get_todays_orders_by_status("Returned By YDM")

        # Complete dashboard data
        data = {
            "overall_statistics": {
                "Total Orders": get_status_stats(
                    [
                        "Sent to YDM",
                        "Verified",
                        "Out For Delivery",
                        "Rescheduled",
                        "Delivered",
                        "Cancelled",
                        "Returned By Customer",
                        "Returned By YDM",
                        "Return Pending",
                    ]
                ),
                "Total COD": get_status_stats(
                    [
                        "Sent to YDM",
                        "Verified",
                        "Out For Delivery",
                        "Rescheduled",
                        "Delivered",
                    ]
                ),
                "Total Delivered": get_status_stats("Delivered"),
                "Total RTV": get_status_stats("Return Pending"),
                "Total Cancelled": get_status_stats(
                    ["Cancelled", "Returned By Customer", "Returned By YDM"]
                ),
                "Total Delivery Charge": {
                    "nos": orders.count(),
                    "amount": total_charge,
                },
                "Total Pending COD": {
                    "nos": get_status_stats("Delivered")["nos"],
                    "amount": max(
                        0, get_status_stats("Delivered")["amount"] - total_charge
                    ),
                },
            },
            "todays_statistics": {
                "Todays Orders": todays_orders_count,
                "Todays Delivery": todays_deliveries_count,
                "Todays Rescheduled": todays_rescheduled_count,
                "Todays Cancellation": todays_cancellations_count,
            },
            "delivery_performance": {
                "Delivered Percentage": delivered_percentage,
                "Cancelled Percentage": cancelled_percentage,
            },
        }

        return Response({"success": True, "data": data}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"success": False, "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
# @permission_classes([IsAuthenticated])
def daily_orders_by_franchise(request, franchise_id):
    """
    Return daily order counts for the given franchise_id with detailed status
    breakdowns based on OrderChangeLog in the current month only (no missing
    days filled). Groups by the date an order changed to a particular status
    and includes counts for both active and cancelled-related statuses.
    """

    today = date.today()
    year, month = today.year, today.month

    # Statuses of interest (aligning with other views used in this module)
    active_statuses = [
        "Sent to YDM",
        "Verified",
        "Out For Delivery",
        "Rescheduled",
        "Delivered",
    ]
    cancelled_statuses = [
        "Cancelled",
        "Returned By Customer",
        "Returned By YDM",
        "Return Pending",
    ]
    statuses_of_interest = active_statuses + cancelled_statuses

    # Pull daily counts and revenue per status from change logs for the current month
    # Step 1: reduce to unique (change_date, new_status, order_id) to avoid double-counting
    unique_logs = (
        OrderChangeLog.objects.filter(
            order__franchise_id=franchise_id,
            order__logistics="YDM",
            new_status__in=statuses_of_interest,
            changed_at__year=year,
            changed_at__month=month,
        )
        .annotate(change_date=TruncDate("changed_at"))
        .values("change_date", "new_status", "order_id")
        .annotate(first_change=Min("id"))
        # Compute net revenue per order row: total_amount - prepaid_amount
        .annotate(
            net_amount=ExpressionWrapper(
                Coalesce(F("order__total_amount"), 0)
                - Coalesce(F("order__prepaid_amount"), 0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
    )

    # Step 2: aggregate by date and status for counts and revenue
    logs = (
        unique_logs.values("change_date", "new_status")
        .annotate(
            count=Count("order_id", distinct=True),
            revenue=Sum("net_amount"),
        )
        .order_by("change_date")
    )

    # Build a date-indexed structure

    date_map = defaultdict(
        lambda: {
            "active_orders": {
                "sent_to_ydm": 0,
                "verified": 0,
                "out_for_delivery": 0,
                "rescheduled": 0,
                "delivered": 0,
            },
            "cancelled_orders": {
                "cancelled": 0,
                "returned_by_customer": 0,
                "returned_by_ydm": 0,
                "return_pending": 0,
            },
            # running sums per day
            "active_total": 0,
            "cancelled_total": 0,
            "active_revenue": Decimal("0"),
            "cancelled_revenue": Decimal("0"),
        }
    )

    # Helper to map raw status to response keys
    status_key_map = {
        "Sent to YDM": ("active_orders", "sent_to_ydm"),
        "Verified": ("active_orders", "verified"),
        "Out For Delivery": ("active_orders", "out_for_delivery"),
        "Rescheduled": ("active_orders", "rescheduled"),
        "Delivered": ("active_orders", "delivered"),
        "Cancelled": ("cancelled_orders", "cancelled"),
        "Returned By Customer": ("cancelled_orders", "returned_by_customer"),
        "Returned By YDM": ("cancelled_orders", "returned_by_ydm"),
        "Return Pending": ("cancelled_orders", "return_pending"),
    }

    for item in logs:
        change_date = item["change_date"]
        status_label = item["new_status"]
        count = item["count"] or 0
        revenue = item.get("revenue") or Decimal("0")
        bucket, key = status_key_map.get(status_label, (None, None))
        if bucket:
            date_map[change_date][bucket][key] += count
            if bucket == "active_orders":
                date_map[change_date]["active_total"] += count
                date_map[change_date]["active_revenue"] += revenue
            elif bucket == "cancelled_orders":
                date_map[change_date]["cancelled_total"] += count
                date_map[change_date]["cancelled_revenue"] += revenue

    # Format response list sorted by date
    formatted_days = []
    for change_date in sorted(date_map.keys()):
        data = date_map[change_date]
        total_count = data["active_total"] + data["cancelled_total"]
        total_revenue = data["active_revenue"] + data["cancelled_revenue"]
        formatted_days.append(
            {
                "date": change_date,
                "active_count": data["active_total"],
                "cancelled_count": data["cancelled_total"],
                "total_count": total_count,
                "active_revenue": str(data["active_revenue"]),
                "cancelled_revenue": str(data["cancelled_revenue"]),
                "total_revenue": str(total_revenue),
                "active_orders": data["active_orders"],
                "cancelled_orders": data["cancelled_orders"],
            }
        )

    return Response(
        {
            "filter_type": "daily",
            "data": formatted_days,
        }
    )


class AssignOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_id = request.data.get("user_id")
        order_ids = request.data.get("order_ids")

        if not user_id or not order_ids:
            return Response(
                {"detail": "user_id and order_ids are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # validate user (must be rider)
        try:
            user = CustomUser.objects.get(id=user_id, role="YDM_Rider")
        except CustomUser.DoesNotExist:
            return Response(
                {"detail": "User not found or is not a YDM Rider"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # validate orders
        orders = Order.objects.filter(id__in=order_ids).prefetch_related(
            "assign_orders__user"
        )
        if orders.count() != len(order_ids):
            return Response(
                {"detail": "One or more orders not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        assignments = []

        for order in orders:
            existing_assignment = order.assign_orders.first()
            if existing_assignment:
                continue
            else:
                assignment = AssignOrder.objects.create(order=order, user=user)
                # Update order status to 'Out For Delivery' when assigned to rider
                if order.order_status != "Out For Delivery":
                    order.order_status = "Out For Delivery"
                    order.save()
                assignments.append(assignment)

        return Response(
            {
                "assigned": AssignOrderSerializer(assignments, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def patch(self, request):
        user_id = request.data.get("user_id")
        order_ids = request.data.get("order_ids")

        if not user_id or not order_ids:
            return Response(
                {"detail": "user_id and order_ids are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # validate user (must be rider)
        try:
            user = CustomUser.objects.get(id=user_id, role="YDM_Rider")
        except CustomUser.DoesNotExist:
            return Response(
                {"detail": "User not found or is not a YDM Rider"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # validate orders
        orders = Order.objects.filter(id__in=order_ids).prefetch_related(
            "assign_orders__user"
        )
        if orders.count() != len(order_ids):
            return Response(
                {"detail": "One or more orders not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        updated = []

        for order in orders:
            # Update or create assignment for each order
            assign_order, created = AssignOrder.objects.update_or_create(
                order=order, defaults={"user": user}
            )

            # Update order status to 'Out For Delivery' when assigned to rider
            if order.order_status != "Out For Delivery":
                order.order_status = "Out For Delivery"
                order.save()

            if created:
                updated.append(
                    {
                        "order_code": order.order_code,
                        "status": "assigned",
                        "assigned_to": user.first_name or user.username,
                        "order_status": "Out For Delivery",
                    }
                )
            else:
                updated.append(
                    {
                        "order_code": order.order_code,
                        "status": "reassigned",
                        "assigned_to": user.first_name or user.username,
                        "order_status": "Out For Delivery",
                    }
                )

        return Response(
            {
                "updated": updated,
            },
            status=status.HTTP_200_OK,
        )


class UpdateOrderStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_ids = request.data.get("order_ids")
        status_value = request.data.get("status")

        if not order_ids or not status_value:
            return Response(
                {"detail": "order_ids and status are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate status value (add more statuses as per your Order model)
        valid_statuses = [
            "Verified",
            "Sent to YDM",
            "Delivered",
            "Cancelled",
            "Rescheduled",
            "Out For Delivery",
            "Returned By Customer",
            "Return Pending",
        ]
        if status_value not in valid_statuses:
            return Response(
                {
                    "detail": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate orders exist
        orders = Order.objects.filter(id__in=order_ids)
        if orders.count() != len(order_ids):
            return Response(
                {"detail": "One or more orders not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        updated_orders = []
        for order in orders:
            if order.order_status != status_value:
                order.order_status = status_value
                order.save()
                updated_orders.append(
                    {
                        "order_id": order.id,
                        "order_code": order.order_code,
                        "previous_status": order.order_status,
                        "new_status": status_value,
                        "updated_at": order.updated_at,
                    }
                )

        return Response(
            {
                "message": f"Successfully updated status for {len(updated_orders)} orders",
                "updated_orders": updated_orders,
            },
            status=status.HTTP_200_OK,
        )


class FranchisePaymentDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, franchise_id):
        """API endpoint showing payment details for a specific franchise"""

        # Get franchise
        franchise = get_object_or_404(Franchise, id=franchise_id)

        # Orders
        orders = Order.objects.filter(franchise=franchise, logistics="YDM")

        total_order_amount = orders.aggregate(total=Sum("total_amount"))[
            "total"
        ] or Decimal("0")

        total_orders = orders.count()
        total_deduction = Decimal("100") * total_orders
        gross_amount = total_order_amount - total_deduction

        # Payments
        total_paid = FranchisePaymentLog.objects.filter(franchise=franchise).aggregate(
            total=Sum("amount_paid")
        )["total"] or Decimal("0")

        pending_amount = gross_amount - total_paid

        return Response(
            {
                "total_orders": total_orders,
                "total_order_amount": str(total_order_amount),
                "total_deduction": str(total_deduction),
                "gross_amount": str(gross_amount),
                "total_paid": str(total_paid),
                "pending_amount": str(pending_amount),
            }
        )


class FranchisePaymentLogAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, franchise_id):
        """API endpoint showing payment details for a specific franchise"""

        # Get franchise
        franchise = get_object_or_404(Franchise, id=franchise_id)

        # Payments
        payments = FranchisePaymentLog.objects.filter(franchise=franchise)

        return Response(FranchisePaymentLogSerializer(payments, many=True).data)


class OrderFilter(django_filters.FilterSet):
    franchise = django_filters.CharFilter(
        field_name="franchise__id", lookup_expr="exact"
    )
    order_status = django_filters.CharFilter(
        field_name="order_status", lookup_expr="exact"
    )

    # for date range - filtering based on first 'sent to YDM' status change
    start_date = django_filters.DateFilter(method="filter_by_ydm_date")
    end_date = django_filters.DateFilter(method="filter_by_ydm_date")

    def filter_by_ydm_date(self, queryset, name, value):
        # Get the most recent 'sent to YDM' status change for each order
        from django.db.models import OuterRef, Subquery

        # Subquery to get the most recent 'sent to YDM' change for each order
        latest_ydm_changes = (
            OrderChangeLog.objects.filter(
                order_id=OuterRef("pk"), new_status="Sent to YDM"
            )
            .order_by("-changed_at")
            .values("changed_at")[:1]
        )

        # Apply the date filter to the input queryset (which already has other filters applied)
        filtered_queryset = queryset.annotate(
            last_ydm_change=Subquery(latest_ydm_changes)
        ).exclude(last_ydm_change__isnull=True)

        if name == "start_date":
            # Filter for orders where the most recent 'sent to YDM' is on or after start_date
            return filtered_queryset.filter(last_ydm_change__date__gte=value)
        else:  # end_date
            # Filter for orders where the most recent 'sent to YDM' is on or before end_date
            return filtered_queryset.filter(last_ydm_change__date__lte=value)

    class Meta:
        model = Order
        fields = [
            "franchise",
            "order_status",
            "start_date",
            "end_date",
        ]


class ExportOrdersCSVView(APIView):
    filter_backends = [DjangoFilterBackend]
    filterset_class = OrderFilter

    def get(self, request):
        qs = Order.objects.filter(logistics="YDM")

        # Apply filters
        filtered_qs = OrderFilter(request.GET, queryset=qs).qs

        if not filtered_qs.exists():
            return Response({"error": "No orders found for given filters."}, status=404)

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="orders_export.csv"'
        writer = csv.writer(response)

        # --- CSV HEADER ---
        writer.writerow(
            [
                "Date",
                "Customer Name",
                "Contact Number",
                "Alternative Number",
                "Address",
                "Product Name(s)",
                "Pre-Paid Amount",
                "Collection Amount",
                "Delivery Charge",
                "Net Amount",
                "Payment Type",
                "Order Status",
            ]
        )

        total_product_price = 0
        total_net_amount = 0

        for order in filtered_qs:
            products = OrderProduct.objects.filter(order=order)
            products_str = ", ".join(
                [f"{p.quantity}-{p.product.product.name}" for p in products]
            )

            product_price = float(order.total_amount - (order.prepaid_amount or 0))
            delivery_charge = 100
            net_amount = product_price - delivery_charge

            # accumulate totals
            total_product_price += product_price
            total_net_amount += net_amount

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

            latest_change_log = order.change_logs.order_by("-changed_at").first()
            changed_at_str = (
                latest_change_log.changed_at.strftime("%Y-%m-%d")
                if latest_change_log
                else ""
            )

            writer.writerow(
                [
                    changed_at_str,
                    order.full_name,
                    order.phone_number,
                    order.alternate_phone_number or "",
                    full_address,
                    products_str,
                    order.prepaid_amount,
                    product_price,
                    delivery_charge,
                    net_amount,
                    payment_type,
                    order.order_status,
                ]
            )

        # --- TOTAL ROW AT THE END ---
        writer.writerow([])
        writer.writerow(
            [
                "",
                "",
                "",
                "",
                "",
                "TOTALS",
                "",
                total_product_price,
                "",
                total_net_amount,
                "",
                "",
            ]
        )

        return response
