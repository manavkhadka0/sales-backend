# views.py
import csv
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import (
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    Max,
    Min,
    OuterRef,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce, TruncDate
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters import rest_framework as django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.filters import SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from account.models import CustomUser
from account.serializers import SmallUserSerializer
from sales.models import Order, OrderProduct

# You'll need to create this serializer
from sales.serializers import OrderSerializer

from .models import (
    AssignOrder,
    Invoice,
    OrderChangeLog,
    OrderComment,
    ReportInvoice,
)
from .serializers import (
    AssignOrderSerializer,
    FranchiseStatementSerializer,
    InvoiceSerializer,
    OrderChangeLogSerializer,
    OrderCommentDetailSerializer,
    OrderCommentSerializer,
    ReportInvoiceSerializer,
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
                    "nos": valid_orders.count(),
                    "amount": total_charge,
                },
                "Total Pending COD": {
                    "nos": get_status_stats("Delivered")["nos"],
                    # Deduct approved invoice paid amounts from pending COD
                    "amount": (
                        lambda: (
                            lambda delivered_amount, approved_paid: max(
                                0, delivered_amount - total_charge - approved_paid
                            )
                        )(
                            get_status_stats("Delivered")["amount"],
                            float(
                                Invoice.objects.filter(
                                    franchise_id=franchise_id, is_approved=True
                                )
                                .aggregate(total=Sum("paid_amount"))
                                .get("total")
                                or 0
                            ),
                        )
                    )(),
                    "has_invoices": Invoice.objects.filter(
                        franchise_id=franchise_id, is_approved=False
                    ).exists(),
                    "number_of_invoices": Invoice.objects.filter(
                        franchise_id=franchise_id, is_approved=False
                    ).count(),
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
def get_total_pending_cod(request, franchise_id):
    """
    Return only the "Total Pending COD" stats as a separate endpoint.

    Logic mirrors the calculation used in get_complete_dashboard_stats:
    - nos: number of Delivered orders
    - amount: max(0, Delivered COD amount - total_charge)
    where total_charge = (valid_delivered_orders * DELIVERY_CHARGE) + (cancelled_orders * CANCELLED_CHARGE)
    """
    try:
        exclude_status = [
            "Pending",
            "Processing",
            "Sent to Dash",
            "Indrive",
            "Return By Dash",
        ]

        orders = Order.objects.filter(
            franchise_id=franchise_id, logistics="YDM"
        ).exclude(order_status__in=exclude_status)

        # Helper function to get stats (count and COD amount) for given status list
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

        # Compute charges identical to dashboard logic
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

        valid_charge = valid_orders * DELIVERY_CHARGE
        cancelled_charge = cancelled_orders * CANCELLED_CHARGE
        total_charge = valid_charge + cancelled_charge

        delivered_stats = get_status_stats("Delivered")
        # Deduct approved invoice paid amounts from pending COD
        approved_paid = (
            Invoice.objects.filter(franchise__id=franchise_id, is_approved=True)
            .aggregate(total=Sum("paid_amount"))
            .get("total")
            or 0
        )
        data = {
            "amount": max(
                0,
                float(delivered_stats["amount"]) - total_charge - float(approved_paid),
            ),
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


@api_view(["GET"])
def daily_delivered_orders(request, franchise_id):
    """
    Return per-day delivered order stats for the current month for a franchise:
    - delivered_count
    - delivered_total_amount (sum of total_amount)
    - delivered_cod_amount (sum of total_amount - prepaid_amount)

    Notes:
    - Uses OrderChangeLog with new_status="Delivered" and groups by the day (TruncDate)
    - Restricts to current month (server timezone) and logistics="YDM"
    - De-duplicates per (change_date, order_id) to avoid double-counting
    - Optional query param `month` (YYYY-MM) can be supported later if needed
    """
    today = timezone.now().date()
    year, month = today.year, today.month

    # Step 1: For each order, get its FIRST Delivered change within current month

    first_delivered_dt = Subquery(
        OrderChangeLog.objects.filter(
            order_id=OuterRef("pk"),
            new_status="Delivered",
            changed_at__year=year,
            changed_at__month=month,
        )
        .order_by("-changed_at")
        .values("changed_at")[:1]
    )

    delivered_orders = (
        Order.objects.filter(franchise_id=franchise_id, logistics="YDM")
        .annotate(first_delivered_dt=first_delivered_dt)
        .exclude(first_delivered_dt__isnull=True)
        .annotate(delivered_date=TruncDate(F("first_delivered_dt")))
    )

    # Step 2: Aggregate per delivered_date (count orders once and sum COD = total - prepaid)
    per_day = (
        delivered_orders.values("delivered_date")
        .annotate(
            delivered_count=Count("id"),
            delivered_total_amount=Sum(
                ExpressionWrapper(
                    Coalesce(
                        F("total_amount"),
                        Value(
                            Decimal("0.00"),
                            output_field=DecimalField(max_digits=12, decimal_places=2),
                        ),
                    )
                    - Coalesce(
                        F("prepaid_amount"),
                        Value(
                            Decimal("0.00"),
                            output_field=DecimalField(max_digits=12, decimal_places=2),
                        ),
                    ),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
        )
        .order_by("-delivered_date")
    )

    # Prepare invoice paid amounts per day (approved invoices only)
    invoice_paid_qs = (
        Invoice.objects.filter(
            franchise__id=franchise_id,
            is_approved=True,
            approved_at__year=year,
            approved_at__month=month,
        )
        .annotate(approved_date=TruncDate("approved_at"))
        .values("approved_date")
        .annotate(
            paid=Coalesce(
                Sum("paid_amount"),
                Value(
                    Decimal("0.00"),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
            )
        )
    )

    invoice_paid_by_date = {
        row["approved_date"]: row["paid"] for row in invoice_paid_qs
    }

    # Get delivered order codes per day (using same logic as main query)
    delivered_orders_qs = delivered_orders.values(
        "delivered_date", "order_code"
    ).order_by("-delivered_date")
    delivered_orders_by_date = defaultdict(list)
    for order in delivered_orders_qs:
        delivered_orders_by_date[order["delivered_date"]].append(order["order_code"])

    # Format response with proper cumulative balance calculation
    results = []
    running_balance = Decimal("0.00")
    # Process dates in chronological order (oldest to newest) for cumulative calculation
    for row in per_day.order_by("delivered_date"):
        d = row["delivered_date"]
        delivered_count = row["delivered_count"] or 0
        delivery_charge_amount = Decimal(str(DELIVERY_CHARGE)) * Decimal(
            delivered_count
        )
        delivered_total_amount_val = row.get("delivered_total_amount") or Decimal(
            "0.00"
        )
        invoice_paid_val = invoice_paid_by_date.get(d, Decimal("0.00"))
        per_day_balance = (
            delivered_total_amount_val - delivery_charge_amount - invoice_paid_val
        )
        running_balance += per_day_balance
        results.append(
            {
                "date": d,
                "delivered_count": delivered_count,
                "delivered_total_amount": str(delivered_total_amount_val),
                "delivered_cod_amount": str(delivery_charge_amount),
                "invoice_paid_amount": str(invoice_paid_val),
                "balance": str(per_day_balance),
                "cumulative_balance": str(running_balance),
                "delivered_orders": delivered_orders_by_date.get(d, []),
            }
        )

    # Reverse results to show newest dates first
    results.reverse()

    # Also include a dashboard-equivalent pending COD (not month-limited) to reconcile numbers
    exclude_status = [
        "Pending",
        "Processing",
        "Sent to Dash",
        "Indrive",
        "Return By Dash",
    ]
    base_orders = Order.objects.filter(
        franchise_id=franchise_id, logistics="YDM"
    ).exclude(order_status__in=exclude_status)
    delivered_agg = base_orders.filter(order_status="Delivered").aggregate(
        count=Count("id"),
        total=Coalesce(
            Sum("total_amount"),
            Value(
                Decimal("0.00"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        ),
        prepaid=Coalesce(
            Sum("prepaid_amount"),
            Value(
                Decimal("0.00"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        ),
    )
    delivered_amount_overall = delivered_agg["total"] - delivered_agg["prepaid"]
    valid_orders_overall = delivered_agg["count"] or 0
    cancelled_overall = Order.objects.filter(
        franchise_id=franchise_id,
        logistics="YDM",
        order_status__in=[
            "Cancelled",
            "Return Pending",
            "Returned By Customer",
            "Returned By YDM",
        ],
    ).count()
    total_charge_overall = (
        Decimal(str(DELIVERY_CHARGE)) * Decimal(valid_orders_overall)
    ) + (Decimal(str(CANCELLED_CHARGE)) * Decimal(cancelled_overall))
    approved_paid_overall = (
        Invoice.objects.filter(franchise__id=franchise_id, is_approved=True)
        .aggregate(
            total=Coalesce(
                Sum("paid_amount"),
                Value(
                    Decimal("0.00"),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
            )
        )
        .get("total")
    )
    pending_cod_equivalent = (
        delivered_amount_overall - total_charge_overall - approved_paid_overall
    )
    if pending_cod_equivalent < 0:
        pending_cod_equivalent = Decimal("0.00")

    # Update the last day's cumulative_balance to match pending_cod_equivalent
    if results:
        results[-1]["cumulative_balance"] = str(pending_cod_equivalent)

    return Response(
        {
            "data": results,
            "pending_cod_equivalent": str(pending_cod_equivalent),
        },
        status=status.HTTP_200_OK,
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
        qs = Order.objects.filter(logistics="YDM").order_by("created_at")

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

            writer.writerow(
                [
                    order.created_at.strftime("%Y-%m-%d"),
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


class CustomPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class InvoiceFilter(django_filters.FilterSet):
    franchise = django_filters.CharFilter(
        field_name="franchise__id", lookup_expr="exact"
    )
    payment_type = django_filters.CharFilter(
        field_name="payment_type", lookup_expr="exact"
    )
    status = django_filters.CharFilter(field_name="status", lookup_expr="exact")
    is_approved = django_filters.BooleanFilter(
        field_name="is_approved", lookup_expr="exact"
    )

    class Meta:
        model = Invoice
        fields = [
            "franchise",
            "payment_type",
            "status",
            "is_approved",
        ]


class InvoiceListCreateView(generics.ListCreateAPIView):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = InvoiceFilter

    def get_queryset(self):
        user = self.request.user
        if not user:
            raise serializers.ValidationError("User is required")
        if user.role == "Franchise":
            return Invoice.objects.filter(franchise=user.franchise)
        if user.role == "YDM_Logistics":
            return Invoice.objects.all()

    def perform_create(self, serializer):
        user = self.request.user
        if not user:
            raise serializers.ValidationError("User is required")

        if user.role != "YDM_Logistics":
            raise serializers.ValidationError("User is not authorized")

        serializer.save(created_by=user)


class InvoiceRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer

    def perform_update(self, serializer):
        """
        If is_approved is being set to True (and was previously False or missing),
        set approved_at to now and approved_by to the current user (if authenticated).
        """
        instance = serializer.instance
        user = self.request.user
        print(user)
        # Determine the new value, defaulting to existing if not provided
        new_is_approved = serializer.validated_data.get(
            "is_approved", instance.is_approved
        )

        # If approving now and there's no approved_at yet, stamp it
        if new_is_approved and (
            not instance.is_approved or instance.approved_at is None
        ):
            serializer.save(
                approved_at=timezone.now(),
                approved_by=user,
                status="Paid",
            )
        else:
            serializer.save()


class InvoiceReportFilter(django_filters.FilterSet):
    invoice = django_filters.CharFilter(field_name="invoice__id", lookup_expr="exact")

    class Meta:
        model = ReportInvoice
        fields = [
            "invoice",
        ]


class InvoiceReportListCreateView(generics.ListCreateAPIView):
    queryset = ReportInvoice.objects.all()
    serializer_class = ReportInvoiceSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = InvoiceReportFilter

    def perform_create(self, serializer):
        user = self.request.user
        if not user:
            raise serializers.ValidationError("User is required")

        serializer.save(reported_by=user)


class InvoiceReportRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ReportInvoice.objects.all()
    serializer_class = ReportInvoiceSerializer


class FranchiseStatementPagination(PageNumberPagination):
    page_size = 30  # Default items per page
    page_size_query_param = "page_size"
    max_page_size = 100


class FranchiseStatementAPIView(generics.ListAPIView):
    serializer_class = FranchiseStatementSerializer
    pagination_class = FranchiseStatementPagination

    def get_queryset(self):
        return []

    def list(self, request, franchise_id=None):
        # 1. Parse date filters
        start_date_param = request.GET.get("start_date")
        end_date_param = request.GET.get("end_date")

        if start_date_param and end_date_param:
            try:
                start_date = datetime.strptime(start_date_param, "%Y-%m-%d").date()
                end_date = datetime.strptime(end_date_param, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Invalid date format. Use YYYY-MM-DD"}, status=400
                )
        else:
            # fallback: detect earliest and latest activity
            earliest_order_created = Order.objects.filter(
                franchise_id=franchise_id, logistics="YDM"
            ).aggregate(Min("created_at"))["created_at__min"]

            earliest_log_sent = OrderChangeLog.objects.filter(
                order__franchise_id=franchise_id,
                order__logistics="YDM",
                new_status="Sent to YDM",
            ).aggregate(Min("changed_at"))["changed_at__min"]

            earliest_delivery = OrderChangeLog.objects.filter(
                order__franchise_id=franchise_id,
                order__logistics="YDM",
                new_status="Delivered",
            ).aggregate(Min("changed_at"))["changed_at__min"]

            earliest_payment = Invoice.objects.filter(
                franchise_id=franchise_id, is_approved=True
            ).aggregate(Min("approved_at"))["approved_at__min"]

            latest_activity = max(
                filter(
                    None,
                    [
                        OrderChangeLog.objects.filter(
                            order__franchise_id=franchise_id,
                            order__logistics="YDM",
                        ).aggregate(Max("changed_at"))["changed_at__max"],
                        Invoice.objects.filter(
                            franchise_id=franchise_id, is_approved=True
                        ).aggregate(Max("approved_at"))["approved_at__max"],
                    ],
                ),
                default=timezone.now(),
            )

            start_date = min(
                filter(
                    None,
                    [
                        earliest_order_created,
                        earliest_log_sent,
                        earliest_delivery,
                        earliest_payment,
                    ],
                ),
                default=date.today(),
            ).date()
            end_date = latest_activity.date() if latest_activity else date.today()

        # 2. Dashboard summary
        dashboard_data = calculate_dashboard_pending_cod(franchise_id)

        # 3. Build statement (optimized)
        # Ensure we include the full date range by extending end_date by 1 day
        extended_end_date = end_date + timedelta(days=1)
        statement_data = generate_order_tracking_statement_optimized(
            franchise_id, start_date, extended_end_date, dashboard_data
        )

        # 4. Apply pagination
        paginator = self.pagination_class()
        paginated_statement = paginator.paginate_queryset(
            statement_data, request, view=self
        )

        serializer = self.serializer_class(paginated_statement, many=True)

        # 5. Return paginated response (DRF style)
        return paginator.get_paginated_response(
            {
                "franchise_id": franchise_id,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "dashboard_pending_cod": float(dashboard_data["pending_cod"]),
                "dashboard_breakdown": {
                    "delivered_amount": float(dashboard_data["delivered_amount"]),
                    "total_order": dashboard_data["total_order"],
                    "total_amount": float(dashboard_data["total_amount"]),
                    "total_charge": float(dashboard_data["total_charge"]),
                    "approved_paid": float(dashboard_data["approved_paid"]),
                    "delivered_count": dashboard_data["delivered_count"],
                    "cancelled_count": dashboard_data["cancelled_count"],
                },
                "statement": serializer.data,
            }
        )


# ---------------- Dashboard Calculation ---------------- #


def calculate_dashboard_pending_cod(franchise_id):
    exclude_status = [
        "Pending",
        "Processing",
        "Sent to Dash",
        "Indrive",
        "Return By Dash",
    ]

    orders = Order.objects.filter(franchise_id=franchise_id, logistics="YDM").exclude(
        order_status__in=exclude_status
    )

    total_order = orders.count()
    total_amount = sum(
        float(o.total_amount or 0) - float(o.prepaid_amount or 0) for o in orders
    )

    delivered_orders = orders.filter(order_status="Delivered")
    delivered_count = delivered_orders.count()
    delivered_amount = sum(
        float(o.total_amount or 0) - float(o.prepaid_amount or 0)
        for o in delivered_orders
    )

    cancelled_orders = orders.filter(
        order_status__in=[
            "Cancelled",
            "Return Pending",
            "Returned By Customer",
            "Returned By YDM",
        ]
    ).count()

    DELIVERY_CHARGE = 100
    total_charge = delivered_count * DELIVERY_CHARGE

    approved_paid = float(
        Invoice.objects.filter(franchise_id=franchise_id, is_approved=True)
        .aggregate(total=Sum("paid_amount"))
        .get("total")
        or 0
    )

    pending_cod = max(0, delivered_amount - total_charge - approved_paid)

    return {
        "pending_cod": pending_cod,
        "total_order": total_order,
        "total_amount": total_amount,
        "delivered_amount": delivered_amount,
        "total_charge": total_charge,
        "approved_paid": approved_paid,
        "delivered_count": delivered_count,
        "cancelled_count": cancelled_orders,
    }


# ---------------- Optimized Statement Generator ---------------- #


def generate_order_tracking_statement_optimized(
    franchise_id, start_date, end_date, dashboard_data
):
    # ---------------- Batch fetch orders ---------------- #
    # Sent to YDM - Get logs within the date range
    sent_logs = OrderChangeLog.objects.filter(
        order__franchise_id=franchise_id,
        order__logistics="YDM",
        new_status="Sent to YDM",
        changed_at__date__range=[start_date, end_date],
    ).values("order_id", "changed_at", "order__total_amount", "order__prepaid_amount")

    sent_orders = {}
    for log in sent_logs:
        order_id = log["order_id"]
        if order_id not in sent_orders:
            sent_orders[order_id] = {
                "sent_date": log["changed_at"].date(),
                "total_amount": float(log["order__total_amount"] or 0)
                - float(log["order__prepaid_amount"] or 0),
            }

    # Orders without logs - Include orders created within the date range that don't have logs
    orders_without_logs = (
        Order.objects.filter(
            franchise_id=franchise_id,
            logistics="YDM",
            created_at__date__range=[start_date, end_date],
        )
        .exclude(id__in=sent_orders.keys())
        .values("id", "created_at", "total_amount", "prepaid_amount")
    )

    for o in orders_without_logs:
        sent_orders[o["id"]] = {
            "sent_date": o["created_at"].date(),
            "total_amount": float(o["total_amount"] or 0)
            - float(o["prepaid_amount"] or 0),
        }

    # Aggregate per day
    daily_sent_orders = defaultdict(list)
    for o in sent_orders.values():
        daily_sent_orders[o["sent_date"]].append(o["total_amount"])

    # ---------------- Delivered orders ---------------- #
    delivered_logs = OrderChangeLog.objects.filter(
        order__franchise_id=franchise_id,
        order__logistics="YDM",
        new_status="Delivered",
        changed_at__date__range=[start_date, end_date],
    ).values("order_id", "changed_at", "order__total_amount", "order__prepaid_amount")

    delivered_orders = {}
    for log in delivered_logs:
        oid = log["order_id"]
        if oid not in delivered_orders:
            delivered_orders[oid] = {
                "delivery_date": log["changed_at"].date(),
                "cash_in": float(log["order__total_amount"] or 0)
                - float(log["order__prepaid_amount"] or 0),
            }

    delivered_without_logs = (
        Order.objects.filter(
            franchise_id=franchise_id,
            logistics="YDM",
            order_status="Delivered",
            updated_at__date__range=[start_date, end_date],
        )
        .exclude(id__in=delivered_orders.keys())
        .values("id", "updated_at", "total_amount", "prepaid_amount")
    )

    for o in delivered_without_logs:
        delivered_orders[o["id"]] = {
            "delivery_date": o["updated_at"].date(),
            "cash_in": float(o["total_amount"] or 0) - float(o["prepaid_amount"] or 0),
        }

    daily_delivered = defaultdict(list)
    for o in delivered_orders.values():
        daily_delivered[o["delivery_date"]].append(o["cash_in"])

    # ---------------- Payments ---------------- #
    payments = (
        Invoice.objects.filter(
            franchise_id=franchise_id,
            is_approved=True,
            approved_at__date__range=[start_date, end_date],
        )
        .values("approved_at__date")
        .annotate(total_payment=Sum("paid_amount"))
    )

    daily_payments = {
        p["approved_at__date"]: float(p["total_payment"] or 0) for p in payments
    }

    # ---------------- Build Statement ---------------- #
    all_dates = (
        set(daily_sent_orders.keys())
        | set(daily_delivered.keys())
        | set(daily_payments.keys())
    )
    statement = []

    # Calculate starting balance - USE SAME LOGIC AS DASHBOARD
    # Get all delivered orders BEFORE the start_date (same as dashboard logic)
    pre_start_delivered_orders = Order.objects.filter(
        franchise_id=franchise_id,
        logistics="YDM",
        order_status="Delivered",
        updated_at__date__lt=start_date,
    )

    pre_start_delivered_amount = sum(
        float(o.total_amount or 0) - float(o.prepaid_amount or 0)
        for o in pre_start_delivered_orders
    )

    pre_start_delivered_count = pre_start_delivered_orders.count()
    pre_start_delivery_charge = pre_start_delivered_count * 100

    pre_start_payments = float(
        Invoice.objects.filter(
            franchise_id=franchise_id,
            is_approved=True,
            approved_at__date__lt=start_date,
        )
        .aggregate(total=Sum("paid_amount"))
        .get("total")
        or 0
    )

    # Starting balance = previous delivered amount - previous delivery charges - previous payments
    running_balance = (
        pre_start_delivered_amount - pre_start_delivery_charge - pre_start_payments
    )

    # For daily calculations, also use Order table instead of logs to avoid duplicates
    for d in sorted(all_dates):
        total_order = len(daily_sent_orders.get(d, []))
        total_amount = sum(daily_sent_orders.get(d, []))

        # Get delivered orders for this date from Order table (same as dashboard)
        daily_delivered_orders = Order.objects.filter(
            franchise_id=franchise_id,
            logistics="YDM",
            order_status="Delivered",
            updated_at__date=d,
        )

        delivery_count = daily_delivered_orders.count()
        cash_in = sum(
            float(o.total_amount or 0) - float(o.prepaid_amount or 0)
            for o in daily_delivered_orders
        )
        delivery_charge = delivery_count * 100
        payment = daily_payments.get(d, 0)

        balance_change = cash_in - delivery_charge - payment
        running_balance += balance_change

        statement.append(
            {
                "date": d.strftime("%Y-%m-%d"),
                "total_order": total_order,
                "total_amount": total_amount,
                "delivery_count": delivery_count,
                "cash_in": cash_in,
                "delivery_charge": delivery_charge,
                "payment": payment,
                "balance": round(running_balance, 2),
            }
        )

    return statement


class SentToYDMCSVExportView(APIView):
    """
    Export CSV data for orders based on status and date filters.
    Supports:
    - Status filtering (e.g., status=delivered)
    - Single date filtering (sent_date=YYYY-MM-DD)
    - Date range filtering (start_date=YYYY-MM-DD&end_date=YYYY-MM-DD)
    """

    def get(self, request):
        # Get parameters
        sent_date = request.GET.get("sent_date")
        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")
        status = request.GET.get("status")
        franchise_id = request.GET.get("franchise_id")

        # Validate date parameters
        if not sent_date and not start_date and not end_date:
            return Response(
                {
                    "error": "At least one date parameter is required: sent_date, start_date, or end_date"
                },
                status=400,
            )

        # Parse dates
        date_filter = None
        date_range_str = ""

        if sent_date:
            # Single date filter
            try:
                date_obj = datetime.strptime(sent_date, "%Y-%m-%d").date()
                date_filter = {"changed_at__date": date_obj}
                date_range_str = sent_date
            except ValueError:
                return Response(
                    {"error": "Invalid sent_date format. Use YYYY-MM-DD"}, status=400
                )
        elif start_date and end_date:
            # Date range filter
            try:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
                date_filter = {
                    "changed_at__date__range": [start_date_obj, end_date_obj]
                }
                date_range_str = f"{start_date}_to_{end_date}"
            except ValueError:
                return Response(
                    {"error": "Invalid date format. Use YYYY-MM-DD"}, status=400
                )
        elif start_date:
            # Only start date - filter from start_date onwards
            try:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
                date_filter = {"changed_at__date__gte": start_date_obj}
                date_range_str = f"from_{start_date}"
            except ValueError:
                return Response(
                    {"error": "Invalid start_date format. Use YYYY-MM-DD"}, status=400
                )
        elif end_date:
            # Only end date - filter up to end_date
            try:
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
                date_filter = {"changed_at__date__lte": end_date_obj}
                date_range_str = f"until_{end_date}"
            except ValueError:
                return Response(
                    {"error": "Invalid end_date format. Use YYYY-MM-DD"}, status=400
                )

        # Get franchise_id from user or query parameter
        if not franchise_id:
            # Try to get from user's franchise
            if hasattr(request.user, "franchise") and request.user.franchise:
                franchise_id = request.user.franchise.id
            else:
                return Response(
                    {"error": "franchise_id parameter is required"}, status=400
                )

        try:
            franchise_id = int(franchise_id)
        except ValueError:
            return Response({"error": "Invalid franchise_id"}, status=400)

        # Determine the status to filter by
        if status:
            # Filter by specific status (e.g., "Delivered", "Sent to YDM")
            status_filter = {"new_status": status}
            status_str = status.lower().replace(" ", "_")
        else:
            # Default to "Sent to YDM" if no status specified
            status_filter = {"new_status": "Sent to YDM"}
            status_str = "sent_to_ydm"

        # Find orders based on status and date filters
        # First, get order IDs from logs
        log_filters = {
            "order__franchise_id": franchise_id,
            "order__logistics": "YDM",
            **status_filter,
            **date_filter,
        }

        sent_logs = OrderChangeLog.objects.filter(**log_filters).values_list(
            "order_id", flat=True
        )

        # Get the actual orders
        orders = (
            Order.objects.filter(id__in=sent_logs)
            .select_related("franchise", "sales_person", "location")
            .prefetch_related("order_products__product__product")
            .order_by("created_at")
        )

        if not orders.exists():
            status_msg = f" with status '{status}'" if status else ""
            return Response(
                {"error": f"No orders found{status_msg} on {date_range_str}"},
                status=404,
            )

        # Create CSV response
        response = HttpResponse(content_type="text/csv")
        filename = f"{status_str}_{date_range_str}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        writer = csv.writer(response)

        # Write CSV header
        status_column_name = f"{status.title()} At" if status else "Sent to YDM At"
        writer.writerow(
            [
                "Date",
                "Order Code",
                "Customer Name",
                "Contact Number",
                "Alternative Number",
                "Address",
                "City",
                "Landmark",
                "Product Details",
                "Total Amount",
                "Prepaid Amount",
                "Collection Amount",
                "Delivery Charge",
                "Net Amount",
                "Payment Method",
                "Order Status",
                "Logistics",
                "Sales Person",
                "Franchise",
                "Created At",
                status_column_name,
                "Remarks",
            ]
        )

        total_orders = 0
        total_amount = 0
        total_collection = 0
        total_delivery_charge = 0
        total_net = 0

        for order in orders:
            # Get the exact time when the status change occurred
            target_status = status if status else "Sent to YDM"
            status_log = (
                order.change_logs.filter(new_status=target_status)
                .order_by("changed_at")
                .first()
            )

            status_changed_at = (
                status_log.changed_at if status_log else order.created_at
            )

            # Format products string
            products = order.order_products.all()
            products_str = ", ".join(
                [f"{p.quantity}-{p.product.product.name}" for p in products]
            )

            # Calculate amounts
            collection_amount = float(order.total_amount or 0) - float(
                order.prepaid_amount or 0
            )
            delivery_charge = 100  # Standard delivery charge
            net_amount = collection_amount - delivery_charge

            # Build address
            address_parts = []
            if order.delivery_address:
                address_parts.append(order.delivery_address)
            if order.city:
                address_parts.append(order.city)
            if order.landmark:
                address_parts.append(order.landmark)
            full_address = ", ".join(address_parts)

            # Determine the date to show in the first column
            if sent_date:
                display_date = sent_date
            elif start_date and end_date:
                display_date = f"{start_date} to {end_date}"
            elif start_date:
                display_date = f"from {start_date}"
            elif end_date:
                display_date = f"until {end_date}"
            else:
                display_date = status_changed_at.strftime("%Y-%m-%d")

            # Write row
            writer.writerow(
                [
                    display_date,  # Date
                    order.order_code,  # Order Code
                    order.full_name,  # Customer Name
                    order.phone_number,  # Contact Number
                    order.alternate_phone_number or "",  # Alternative Number
                    order.delivery_address or "",  # Address
                    order.city or "",  # City
                    order.landmark or "",  # Landmark
                    products_str,  # Product Details
                    float(order.total_amount or 0),  # Total Amount
                    float(order.prepaid_amount or 0),  # Prepaid Amount
                    collection_amount,  # Collection Amount
                    delivery_charge,  # Delivery Charge
                    net_amount,  # Net Amount
                    order.payment_method,  # Payment Method
                    order.order_status,  # Order Status
                    order.logistics,  # Logistics
                    order.sales_person.get_full_name()
                    if order.sales_person
                    else "",  # Sales Person
                    order.franchise.name if order.franchise else "",  # Franchise
                    order.created_at.strftime("%Y-%m-%d %H:%M:%S"),  # Created At
                    status_changed_at.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),  # Status Changed At
                    order.remarks or "",  # Remarks
                ]
            )

            # Update totals
            total_orders += 1
            total_amount += float(order.total_amount or 0)
            total_collection += collection_amount
            total_delivery_charge += delivery_charge
            total_net += net_amount

        # Add summary row
        writer.writerow([])  # Empty row
        writer.writerow(["SUMMARY"])
        writer.writerow(["Total Orders", total_orders])
        writer.writerow(["Total Amount", total_amount])
        writer.writerow(["Total Collection", total_collection])
        writer.writerow(["Total Delivery Charge", total_delivery_charge])
        writer.writerow(["Total Net Amount", total_net])

        return response
