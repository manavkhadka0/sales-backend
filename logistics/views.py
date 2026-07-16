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
from rest_framework import filters as rest_filters
from rest_framework import generics, serializers, status
from rest_framework.decorators import api_view, permission_classes
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
from sales.models import Order

# You'll need to create this serializer
from sales.serializers import OrderSerializer

from .models import (
    AssignOrder,
    Invoice,
    OrderChangeLog,
    OrderComment,
    ReportInvoice,
    RiderCommissionRate,
    RiderPayout,
    YdmLogisticsSetting,
)
from .serializers import (
    AssignOrderSerializer,
    FranchiseStatementSerializer,
    InvoiceSerializer,
    OrderChangeLogSerializer,
    OrderCommentDetailSerializer,
    OrderCommentSerializer,
    ReportInvoiceSerializer,
    RiderCommissionRateSerializer,
    RiderPayoutSerializer,
    YdmLogisticsSettingSerializer,
)


class CustomPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


DELIVERY_CHARGE = 100
CANCELLED_CHARGE = 0


class GetYDMRiderView(generics.ListAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = SmallUserSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [rest_filters.SearchFilter]
    pagination_class = CustomPagination
    search_fields = ["first_name", "phone_number", "address"]

    def get_queryset(self):
        return CustomUser.objects.filter(role="YDM_Rider", is_deleted=False)


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

    return Response({
        "order": serializer.data,
        "order_change_log": order_change_log.data,
        "order_comment": order_comment.data,
    })


@api_view(["GET"])
def get_franchise_order_stats(request, franchise_id):
    """
    Get order statistics for a franchise where logistics is YDM
    """
    try:
        # Parse optional date range filters
        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")
        try:
            start_date = (
                timezone.datetime.strptime(start_date_str, "%Y-%m-%d").date()
                if start_date_str
                else None
            )
            end_date = (
                timezone.datetime.strptime(end_date_str, "%Y-%m-%d").date()
                if end_date_str
                else None
            )
        except ValueError:
            return Response(
                {"success": False, "message": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Base queryset
        orders = Order.objects.filter(
            franchise_id=franchise_id, logistics="YDM"
        ).exclude(
            order_status__in=[
                "Pending",
                "Processing",
                "Sent to Dash",
                "Sent to Daraz",
                "Indrive",
                "Returned By PicknDrop",
                "Sent to PicknDrop",
                "Returned By Dash",
                "Returned By Daraz",
            ]
        )

        if start_date:
            orders = orders.filter(created_at__date__gte=start_date)
        if end_date:
            orders = orders.filter(created_at__date__lte=end_date)

        # Optimize by pre-aggregating in one query
        status_aggregates = orders.values("order_status").annotate(
            count=Count("id"),
            total=Sum("total_amount"),
            prepaid=Sum("prepaid_amount"),
        )
        stats_by_status = {
            row["order_status"]: {
                "count": row["count"],
                "total": float(row["total"] or 0),
                "prepaid": float(row["prepaid"] or 0),
            }
            for row in status_aggregates
        }

        # Helper function to get stats from pre-aggregated dictionary
        def get_status_stats(statuses):
            if isinstance(statuses, str):
                statuses = [statuses]
            total_count = 0
            total_amount = 0.0
            for status_label in statuses:
                st = stats_by_status.get(status_label)
                if st:
                    total_count += st["count"]
                    total_amount += st["total"] - st["prepaid"]
            return {"nos": total_count, "amount": total_amount}

        # Calculate statistics
        data = {
            "Total Orders": get_status_stats([
                "Sent to YDM",
                "Verified",
                "Out For Delivery",
                "Rescheduled",
                "Delivered",
                "Cancelled",
                "Returned By Customer",
                "Returned By YDM",
                "Return Pending",
            ]),
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
            "Sent to Daraz",
            "Indrive",
            "Returned By PicknDrop",
            "Sent to PicknDrop",
            "Returned By Dash",
            "Returned By Daraz",
        ]

        # Parse optional date range filters
        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")
        try:
            start_date = (
                timezone.datetime.strptime(start_date_str, "%Y-%m-%d").date()
                if start_date_str
                else None
            )
            end_date = (
                timezone.datetime.strptime(end_date_str, "%Y-%m-%d").date()
                if end_date_str
                else None
            )
        except ValueError:
            return Response(
                {"success": False, "message": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Base queryset - filter by user's organization
        orders = Order.objects.filter(
            franchise_id=franchise_id, logistics="YDM"
        ).exclude(order_status__in=exclude_status)

        if start_date:
            orders = orders.filter(created_at__date__gte=start_date)
        if end_date:
            orders = orders.filter(created_at__date__lte=end_date)

        # Optimize by pre-aggregating in one query
        status_aggregates = orders.values("order_status").annotate(
            count=Count("id"),
            total=Sum("total_amount"),
            prepaid=Sum("prepaid_amount"),
        )
        stats_by_status = {
            row["order_status"]: {
                "count": row["count"],
                "total": float(row["total"] or 0),
                "prepaid": float(row["prepaid"] or 0),
            }
            for row in status_aggregates
        }

        # Helper function to get stats from pre-aggregated dictionary
        def get_status_stats(statuses):
            if isinstance(statuses, str):
                statuses = [statuses]
            total_count = 0
            total_amount = 0.0
            for status_label in statuses:
                st = stats_by_status.get(status_label)
                if st:
                    total_count += st["count"]
                    total_amount += st["total"] - st["prepaid"]
            return {"nos": total_count, "amount": total_amount}

        # Calculate cancelled orders using the stats_by_status
        cancelled_orders = 0
        for status_label in [
            "Cancelled",
            "Return Pending",
            "Returned By Customer",
            "Returned By YDM",
        ]:
            st = stats_by_status.get(status_label)
            if st:
                cancelled_orders += st["count"]

        # Calculate total charges from actual ydm_delivery_charge and ydm_cancelled_charge set on AssignOrder
        assign_order_qs = AssignOrder.objects.filter(
            order__franchise_id=franchise_id,
            order__logistics="YDM",
        )
        if start_date:
            assign_order_qs = assign_order_qs.filter(
                order__created_at__date__gte=start_date
            )
        if end_date:
            assign_order_qs = assign_order_qs.filter(
                order__created_at__date__lte=end_date
            )
        valid_charge = (
            assign_order_qs.filter(order__order_status="Delivered").aggregate(
                total=Sum("ydm_delivery_charge")
            )["total"]
            or 0
        )
        cancelled_charge = (
            assign_order_qs.filter(
                order__order_status__in=[
                    "Cancelled",
                    "Return Pending",
                    "Returned By Customer",
                    "Returned By YDM",
                ]
            ).aggregate(total=Sum("ydm_cancelled_charge"))["total"]
            or 0
        )

        # Calculate delivery performance percentages
        completed_orders = 0
        for status_label in ["Delivered", "Returned By YDM"]:
            st = stats_by_status.get(status_label)
            if st:
                completed_orders += st["count"]

        delivered_count = stats_by_status.get("Delivered", {}).get("count", 0)
        cancelled_count = stats_by_status.get("Returned By YDM", {}).get("count", 0)

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

        # Optimize today's statistics: do a single query to get today's change logs
        todays_logs = list(
            OrderChangeLog.objects.filter(
                changed_at__date=today,
                order__franchise_id=franchise_id,
                order__logistics="YDM",
                new_status__in=[
                    "Sent to YDM",
                    "Delivered",
                    "Rescheduled",
                    "Returned By YDM",
                ],
            ).values("order_id", "new_status")
        )

        todays_orders_sent = set()
        todays_orders_delivered = set()
        todays_orders_rescheduled = set()
        todays_orders_rtv = set()
        for log in todays_logs:
            status_label = log["new_status"]
            oid = log["order_id"]
            if status_label == "Sent to YDM":
                todays_orders_sent.add(oid)
            elif status_label == "Delivered":
                todays_orders_delivered.add(oid)
            elif status_label == "Rescheduled":
                todays_orders_rescheduled.add(oid)
            elif status_label == "Returned By YDM":
                todays_orders_rtv.add(oid)

        todays_orders_count = len(todays_orders_sent)
        todays_deliveries_count = len(todays_orders_delivered)
        todays_rescheduled_count = len(todays_orders_rescheduled)
        todays_cancellations_count = len(todays_orders_rtv)

        # Complete dashboard data
        data = {
            "overall_statistics": {
                "Total Orders": get_status_stats([
                    "Sent to YDM",
                    "Verified",
                    "Out For Delivery",
                    "Rescheduled",
                    "Delivered",
                    "Cancelled",
                    "Returned By Customer",
                    "Returned By YDM",
                    "Return Pending",
                ]),
                "Total COD": get_status_stats([
                    "Sent to YDM",
                    "Verified",
                    "Out For Delivery",
                    "Rescheduled",
                    "Delivered",
                ]),
                "Total Delivered": get_status_stats("Delivered"),
                "Total RTV": get_status_stats("Return Pending"),
                "Total Cancelled": get_status_stats([
                    "Cancelled",
                    "Returned By Customer",
                    "Returned By YDM",
                ]),
                "Total Delivery Charge": {
                    "nos": assign_order_qs.filter(
                        order__order_status="Delivered"
                    ).count(),
                    "amount": valid_charge,
                },
                "Total Cancellation Charge": {
                    "nos": assign_order_qs.filter(
                        order__order_status__in=[
                            "Cancelled",
                            "Return Pending",
                            "Returned By Customer",
                            "Returned By YDM",
                        ]
                    ).count(),
                    "amount": cancelled_charge,
                },
                "Total Pending COD": {
                    "nos": get_status_stats("Delivered")["nos"],
                    # Deduct approved invoice paid amounts, delivery charge, and cancellation charge from pending COD
                    "amount": (
                        lambda: (
                            lambda delivered_amount, approved_paid: max(
                                0,
                                delivered_amount
                                - float(valid_charge)
                                - float(cancelled_charge)
                                - approved_paid,
                            )
                        )(
                            get_status_stats("Delivered")["amount"],
                            float(
                                Invoice.objects
                                .filter(franchise_id=franchise_id, is_approved=True)
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
            "Sent to Daraz",
            "Indrive",
            "Returned By PicknDrop",
            "Sent to PicknDrop",
            "Returned By Dash",
            "Returned By Daraz",
        ]

        orders = Order.objects.filter(
            franchise_id=franchise_id, logistics="YDM"
        ).exclude(order_status__in=exclude_status)

        # Optimize by pre-aggregating in one query
        status_aggregates = orders.values("order_status").annotate(
            count=Count("id"),
            total=Sum("total_amount"),
            prepaid=Sum("prepaid_amount"),
        )
        stats_by_status = {
            row["order_status"]: {
                "count": row["count"],
                "total": float(row["total"] or 0),
                "prepaid": float(row["prepaid"] or 0),
            }
            for row in status_aggregates
        }

        # Helper function to get stats from pre-aggregated dictionary
        def get_status_stats(statuses):
            if isinstance(statuses, str):
                statuses = [statuses]
            total_count = 0
            total_amount = 0.0
            for status_label in statuses:
                st = stats_by_status.get(status_label)
                if st:
                    total_count += st["count"]
                    total_amount += st["total"] - st["prepaid"]
            return {"nos": total_count, "amount": total_amount}

        # Calculate cancelled orders using stats_by_status
        cancelled_orders = 0
        for status_label in [
            "Cancelled",
            "Return Pending",
            "Returned By Customer",
            "Returned By YDM",
        ]:
            st = stats_by_status.get(status_label)
            if st:
                cancelled_orders += st["count"]

        assign_order_qs = AssignOrder.objects.filter(
            order__franchise_id=franchise_id,
            order__logistics="YDM",
        )
        valid_charge = (
            assign_order_qs.filter(order__order_status="Delivered").aggregate(
                total=Sum("ydm_delivery_charge")
            )["total"]
            or 0
        )
        cancelled_charge = (
            assign_order_qs.filter(
                order__order_status__in=[
                    "Cancelled",
                    "Return Pending",
                    "Returned By Customer",
                    "Returned By YDM",
                ]
            ).aggregate(total=Sum("ydm_cancelled_charge"))["total"]
            or 0
        )
        total_charge = float(valid_charge) + float(cancelled_charge)

        delivered_stats = get_status_stats("Delivered")
        # Deduct approved invoice paid amounts from pending COD
        approved_paid = (
            Invoice.objects
            .filter(franchise__id=franchise_id, is_approved=True)
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
        OrderChangeLog.objects
        .filter(
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
        unique_logs
        .values("change_date", "new_status")
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
        formatted_days.append({
            "date": change_date,
            "active_count": data["active_total"],
            "cancelled_count": data["cancelled_total"],
            "total_count": total_count,
            "active_revenue": str(data["active_revenue"]),
            "cancelled_revenue": str(data["cancelled_revenue"]),
            "total_revenue": str(total_revenue),
            "active_orders": data["active_orders"],
            "cancelled_orders": data["cancelled_orders"],
        })

    return Response({
        "filter_type": "daily",
        "data": formatted_days,
    })


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
        OrderChangeLog.objects
        .filter(
            order_id=OuterRef("pk"),
            new_status="Delivered",
            changed_at__year=year,
            changed_at__month=month,
        )
        .order_by("-changed_at")
        .values("changed_at")[:1]
    )

    delivered_orders = (
        Order.objects
        .filter(franchise_id=franchise_id, logistics="YDM")
        .annotate(first_delivered_dt=first_delivered_dt)
        .exclude(first_delivered_dt__isnull=True)
        .annotate(delivered_date=TruncDate(F("first_delivered_dt")))
    )

    # Step 2: Aggregate per delivered_date (count orders once and sum COD = total - prepaid)
    per_day = (
        delivered_orders
        .values("delivered_date")
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
        Invoice.objects
        .filter(
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

    # Fetch monthly YDM delivery charges grouped by delivery date in a single query to eliminate N+1 loop queries
    first_delivered_dt_sub = Subquery(
        OrderChangeLog.objects
        .filter(
            order_id=OuterRef("order_id"),
            new_status="Delivered",
            changed_at__year=year,
            changed_at__month=month,
        )
        .order_by("-changed_at")
        .values("changed_at")[:1]
    )

    ydm_charges_by_date = (
        AssignOrder.objects
        .filter(
            order__franchise_id=franchise_id,
            order__logistics="YDM",
            order__order_status="Delivered",
            ydm_delivery_charge__isnull=False,
        )
        .annotate(first_del_dt=first_delivered_dt_sub)
        .exclude(first_del_dt__isnull=True)
        .annotate(d_date=TruncDate("first_del_dt"))
        .values("d_date")
        .annotate(total=Sum("ydm_delivery_charge"))
    )

    ydm_charge_map = {row["d_date"]: row["total"] for row in ydm_charges_by_date}

    # Format response with proper cumulative balance calculation
    results = []
    running_balance = Decimal("0.00")
    # Process dates in chronological order (oldest to newest) for cumulative calculation
    for row in per_day.order_by("delivered_date"):
        d = row["delivered_date"]
        delivered_count = row["delivered_count"] or 0
        # Sum actual ydm_delivery_charge set by riders for delivered orders on this date
        date_ydm_charge = ydm_charge_map.get(d, Decimal("0.00"))
        delivery_charge_amount = Decimal(str(date_ydm_charge))
        delivered_total_amount_val = row.get("delivered_total_amount") or Decimal(
            "0.00"
        )
        invoice_paid_val = invoice_paid_by_date.get(d, Decimal("0.00"))
        per_day_balance = (
            delivered_total_amount_val - delivery_charge_amount - invoice_paid_val
        )
        running_balance += per_day_balance
        results.append({
            "date": d,
            "delivered_count": delivered_count,
            "delivered_total_amount": str(delivered_total_amount_val),
            "delivered_cod_amount": str(delivery_charge_amount),
            "invoice_paid_amount": str(invoice_paid_val),
            "balance": str(per_day_balance),
            "cumulative_balance": str(running_balance),
            "delivered_orders": delivered_orders_by_date.get(d, []),
        })

    # Reverse results to show newest dates first
    results.reverse()

    # Also include a dashboard-equivalent pending COD (not month-limited) to reconcile numbers
    exclude_status = [
        "Pending",
        "Processing",
        "Sent to Dash",
        "Sent to Daraz",
        "Indrive",
        "Returned By PicknDrop",
        "Sent to PicknDrop",
        "Returned By Dash",
        "Returned By Daraz",
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
    total_charge_overall = (
        Decimal(
            str(
                AssignOrder.objects.filter(
                    order__franchise_id=franchise_id,
                    order__logistics="YDM",
                    order__order_status="Delivered",
                ).aggregate(total=Sum("ydm_delivery_charge"))["total"]
                or 0
            )
        )
    ) + Decimal(
        str(
            AssignOrder.objects.filter(
                order__franchise_id=franchise_id,
                order__logistics="YDM",
                order__order_status__in=[
                    "Cancelled",
                    "Return Pending",
                    "Returned By Customer",
                    "Returned By YDM",
                ],
            ).aggregate(total=Sum("ydm_cancelled_charge"))["total"]
            or 0
        )
    )
    approved_paid_overall = (
        Invoice.objects
        .filter(franchise__id=franchise_id, is_approved=True)
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
        is_rider_verified = request.data.get("is_rider_verified", False)

        if isinstance(is_rider_verified, str):
            is_rider_verified = is_rider_verified.lower() in ["true", "1", "yes", "y"]
        else:
            is_rider_verified = bool(is_rider_verified)

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
                if is_rider_verified != existing_assignment.is_rider_verified:
                    existing_assignment.is_rider_verified = is_rider_verified
                    existing_assignment.save()
                continue
            else:
                assignment = AssignOrder.objects.create(
                    order=order, user=user, is_rider_verified=is_rider_verified
                )
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
        is_rider_verified = request.data.get("is_rider_verified", None)

        if is_rider_verified is not None:
            if isinstance(is_rider_verified, str):
                is_rider_verified = is_rider_verified.lower() in [
                    "true",
                    "1",
                    "yes",
                    "y",
                ]
            else:
                is_rider_verified = bool(is_rider_verified)

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
            defaults = {"user": user}
            if is_rider_verified is not None:
                defaults["is_rider_verified"] = is_rider_verified

            assign_order, created = AssignOrder.objects.update_or_create(
                order=order, defaults=defaults
            )

            # Update order status to 'Out For Delivery' when assigned to rider
            if order.order_status != "Out For Delivery":
                order.order_status = "Out For Delivery"
                order.save()

            if created:
                updated.append({
                    "order_code": order.order_code,
                    "status": "assigned",
                    "assigned_to": user.first_name or user.username,
                    "order_status": "Out For Delivery",
                    "is_rider_verified": assign_order.is_rider_verified,
                })
            else:
                updated.append({
                    "order_code": order.order_code,
                    "status": "reassigned",
                    "assigned_to": user.first_name or user.username,
                    "order_status": "Out For Delivery",
                    "is_rider_verified": assign_order.is_rider_verified,
                })

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
                updated_orders.append({
                    "order_id": order.id,
                    "order_code": order.order_code,
                    "previous_status": order.order_status,
                    "new_status": status_value,
                    "updated_at": order.updated_at,
                })

        return Response(
            {
                "message": f"Successfully updated status for {len(updated_orders)} orders",
                "updated_orders": updated_orders,
            },
            status=status.HTTP_200_OK,
        )


class RiderVerifyOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.role != "YDM_Rider":
            return Response(
                {"detail": "Only YDM Riders can verify orders."},
                status=status.HTTP_403_FORBIDDEN,
            )

        order_code = request.data.get("order")
        if not order_code:
            return Response(
                {"detail": "order_code is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        delivery_location_type = request.data.get("delivery_location_type")
        if delivery_location_type not in ["Inside Ringroad", "Outside Ringroad"]:
            return Response(
                {
                    "detail": "delivery_location_type is required and must be either 'Inside Ringroad' or 'Outside Ringroad'."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get settings
        setting = YdmLogisticsSetting.objects.first()
        if not setting:
            setting = YdmLogisticsSetting.objects.create(
                inside_ringroad_charge=Decimal("100.00"),
                outside_ringroad_charge=Decimal("150.00"),
            )

        if delivery_location_type == "Inside Ringroad":
            charge = setting.inside_ringroad_charge
        else:
            charge = setting.outside_ringroad_charge

        # Find the assignment for this rider and order
        try:
            assignment = AssignOrder.objects.get(
                user=user, order__order_code=order_code
            )
        except AssignOrder.DoesNotExist:
            return Response(
                {"detail": "No assignment found for this rider and order code."},
                status=status.HTTP_404_NOT_FOUND,
            )

        assignment.is_rider_verified = True
        assignment.delivery_location_type = delivery_location_type
        assignment.ydm_delivery_charge = charge
        assignment.save()

        return Response(
            {
                "detail": "Successfully verified the order.",
                "order_code": order_code,
                "is_rider_verified": True,
                "delivery_location_type": delivery_location_type,
                "ydm_delivery_charge": str(charge),
            },
            status=status.HTTP_200_OK,
        )


class RiderCommissionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role not in ["YDM_Rider", "YDM_Operator", "YDM_Logistics"]:
            return Response(
                {"detail": "You do not have permission to view rider commissions."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # If user is a rider, they view their own. Others can pass rider_id parameter.
        if user.role == "YDM_Rider":
            rider = user
        else:
            rider_id = request.query_params.get("rider")
            if not rider_id:
                return Response(
                    {
                        "detail": "rider_id query parameter is required for non-rider users."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                rider = CustomUser.objects.get(phone_number=rider_id, role="YDM_Rider")
            except CustomUser.DoesNotExist:
                return Response(
                    {"detail": "Rider not found or is not a YDM Rider."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # Get all delivered orders assigned to this rider
        # We find the orders through AssignOrder
        assignments = AssignOrder.objects.filter(
            user=rider,
            order__order_status__in=[
                "Delivered",
            ],
        ).select_related("order")

        orders_data = []
        total_commission_earned = 0

        # Fetch DB rates once to optimize
        rates = list(RiderCommissionRate.objects.all().order_by("order_min_amount"))

        for assignment in assignments:
            order = assignment.order
            amount = order.total_amount

            # Calculate commission
            commission = 0
            if rates:
                for rate in rates:
                    if rate.order_min_amount <= amount and (
                        rate.order_max_amount is None or amount <= rate.order_max_amount
                    ):
                        commission = float(rate.commission_amount)
                        break
            else:
                # Fallback default rules:
                # 199=0, 200=> 249<= 25, 250=>= 349 =30, 350 > 449= 35, 450> 40
                if amount <= 199:
                    commission = 0
                elif 200 <= amount <= 249:
                    commission = 25
                elif 250 <= amount <= 349:
                    commission = 30
                elif 350 <= amount <= 449:
                    commission = 35
                else:
                    commission = 40

            total_commission_earned += commission
            orders_data.append({
                "order_id": order.id,
                "order_code": order.order_code,
                "customer_name": order.full_name,
                "total_amount": float(order.total_amount),
                "order_status": order.order_status,
                "delivery_date": order.updated_at,
                "commission": commission,
            })

        # Get payout records for this rider
        payouts = RiderPayout.objects.filter(rider=rider)
        total_payout = payouts.aggregate(total=Sum("amount"))["total"] or 0
        total_payout = float(total_payout)

        payouts_data = [
            {
                "id": payout.id,
                "amount": float(payout.amount),
                "paid_at": payout.paid_at,
                "remarks": payout.remarks,
            }
            for payout in payouts
        ]

        remaining_balance = total_commission_earned - total_payout

        return Response(
            {
                "rider": {
                    "id": rider.id,
                    "username": rider.username,
                    "first_name": rider.first_name,
                    "last_name": rider.last_name,
                    "email": rider.email,
                    "phone": rider.phone_number,
                },
                "summary": {
                    "total_delivered_orders": len(orders_data),
                    "total_commission_earned": total_commission_earned,
                    "total_commission_paid": total_payout,
                    "remaining_balance": remaining_balance,
                },
                "delivered_orders": orders_data,
                "payouts": payouts_data,
            },
            status=status.HTTP_200_OK,
        )


class RiderPayoutView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RiderPayoutSerializer
    pagination_class = CustomPagination

    def get_queryset(self):
        user = self.request.user

        if user.role not in ["YDM_Rider", "YDM_Operator", "YDM_Logistics"]:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You do not have permission to view rider payouts.")

        # Get target rider
        if user.role == "YDM_Rider":
            rider = user
        else:
            rider_id = self.request.query_params.get("rider")
            if not rider_id:
                from rest_framework.exceptions import ValidationError

                raise ValidationError({
                    "detail": "rider query parameter (phone number) is required for non-rider users."
                })
            try:
                rider = CustomUser.objects.get(phone_number=rider_id, role="YDM_Rider")
            except CustomUser.DoesNotExist:
                from rest_framework.exceptions import NotFound

                raise NotFound({"detail": "Rider not found or is not a YDM Rider."})

        return RiderPayout.objects.filter(rider=rider).order_by("-paid_at")

    def create(self, request, *args, **kwargs):
        if request.user.role not in ["YDM_Logistics", "YDM_Operator"]:
            return Response(
                {"detail": "You do not have permission to log payouts."},
                status=status.HTTP_403_FORBIDDEN,
            )

        rider_id = request.data.get("rider")
        amount = request.data.get("amount")
        remarks = request.data.get("remarks", "")

        if not rider_id or amount is None:
            return Response(
                {"detail": "rider_id and amount are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            rider = CustomUser.objects.get(phone_number=rider_id, role="YDM_Rider")
        except CustomUser.DoesNotExist:
            return Response(
                {"detail": "Rider not found or is not a YDM Rider."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            amount_decimal = Decimal(str(amount))
            if amount_decimal <= 0:
                raise ValueError
        except Exception:
            return Response(
                {"detail": "Amount must be a positive decimal number."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payout = RiderPayout.objects.create(
            rider=rider, amount=amount_decimal, remarks=remarks
        )

        serializer = self.get_serializer(payout)
        return Response(
            {
                "detail": "Payout registered successfully.",
                "payout": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class RiderCommissionStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role not in ["YDM_Rider", "YDM_Operator", "YDM_Logistics"]:
            return Response(
                {
                    "detail": "You do not have permission to view rider commission statistics."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get target rider
        rider_id = request.query_params.get("rider")
        if rider_id:
            try:
                rider = CustomUser.objects.get(phone_number=rider_id, role="YDM_Rider")
            except CustomUser.DoesNotExist:
                return Response(
                    {"detail": "Rider not found or is not a YDM Rider."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            if user.role == "YDM_Rider":
                rider = user
            else:
                return Response(
                    {
                        "detail": "rider_id query parameter is required for non-rider users."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Lifetime Stats
        lifetime_delivered_query = AssignOrder.objects.filter(
            user=rider, order__order_status="Delivered"
        )
        num_orders = lifetime_delivered_query.count()

        # Calculate commission for lifetime
        rates = list(RiderCommissionRate.objects.all().order_by("order_min_amount"))
        commission_per_order = 0
        if rates:
            for rate in rates:
                if rate.order_min_amount <= num_orders and (
                    rate.order_max_amount is None or num_orders <= rate.order_max_amount
                ):
                    commission_per_order = float(rate.commission_amount)
                    break
        else:
            if num_orders <= 199:
                commission_per_order = 0
            elif 200 <= num_orders <= 249:
                commission_per_order = 25
            elif 250 <= num_orders <= 349:
                commission_per_order = 30
            elif 350 <= num_orders <= 449:
                commission_per_order = 35
            else:
                commission_per_order = 40

        lifetime_commission_earned = num_orders * commission_per_order

        # Fetch payouts
        payouts = RiderPayout.objects.filter(rider=rider)
        total_payout = payouts.aggregate(total=Sum("amount"))["total"] or 0
        total_payout = float(total_payout)
        remaining_balance = lifetime_commission_earned - total_payout

        return Response(
            {
                "lifetime_commission_earned": lifetime_commission_earned,
                "lifetime_commission_paid": total_payout,
                "remaining_balance": remaining_balance,
            },
            status=status.HTTP_200_OK,
        )


class RiderPackageStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role not in ["YDM_Rider", "YDM_Operator", "YDM_Logistics"]:
            return Response(
                {
                    "detail": "You do not have permission to view rider package statistics."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get target rider
        if user.role == "YDM_Rider":
            rider = user
        else:
            rider_id = request.query_params.get("rider")
            if not rider_id:
                return Response(
                    {
                        "detail": "rider_id query parameter is required for non-rider users."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                rider = CustomUser.objects.get(phone_number=rider_id, role="YDM_Rider")
            except CustomUser.DoesNotExist:
                return Response(
                    {"detail": "Rider not found or is not a YDM Rider."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # Parse date filters (default to today)
        # Parse date filters (default to today)
        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")

        today = timezone.localdate()

        try:
            start_date = (
                datetime.strptime(start_date_str, "%Y-%m-%d").date()
                if start_date_str
                else today
            )
            end_date = (
                datetime.strptime(end_date_str, "%Y-%m-%d").date()
                if end_date_str
                else today
            )
        except ValueError:
            return Response(
                {
                    "detail": "Invalid date format. Use YYYY-MM-DD for start_date and end_date."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get assigned packages in the date range
        total_assigned_in_range = AssignOrder.objects.filter(
            user=rider,
            assigned_at__date__gte=start_date,
            assigned_at__date__lte=end_date,
        ).count()

        # Get delivered packages in the date range
        total_delivered_in_range = AssignOrder.objects.filter(
            user=rider,
            order__order_status="Delivered",
            assigned_at__date__gte=start_date,
            assigned_at__date__lte=end_date,
        ).count()

        # Lifetime Stats
        lifetime_delivered_count = AssignOrder.objects.filter(
            user=rider, order__order_status="Delivered"
        ).count()

        lifetime_cancelled_count = AssignOrder.objects.filter(
            user=rider, order__order_status="Cancelled"
        ).count()

        return Response(
            {
                "packages_assigned": total_assigned_in_range,
                "packages_delivered": total_delivered_in_range,
                "total_packages_delivered_lifetime": lifetime_delivered_count,
                "total_packages_cancelled_lifetime": lifetime_cancelled_count,
            },
            status=status.HTTP_200_OK,
        )


class RiderOrderFilter(django_filters.FilterSet):
    order_status = django_filters.CharFilter(
        field_name="order_status", lookup_expr="exact"
    )
    city = django_filters.CharFilter(field_name="city", lookup_expr="icontains")
    payment_method = django_filters.CharFilter(
        field_name="payment_method", lookup_expr="icontains"
    )
    delivery_type = django_filters.CharFilter(
        field_name="delivery_type", lookup_expr="icontains"
    )
    start_date = django_filters.DateFilter(
        field_name="assign_orders__assigned_at__date", lookup_expr="gte"
    )
    end_date = django_filters.DateFilter(
        field_name="assign_orders__assigned_at__date", lookup_expr="lte"
    )

    class Meta:
        model = Order
        fields = [
            "order_status",
            "start_date",
            "end_date",
            "city",
            "payment_method",
            "delivery_type",
        ]


class RiderOrdersListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    serializer_class = OrderSerializer
    filterset_class = RiderOrderFilter
    filter_backends = [
        DjangoFilterBackend,
        rest_filters.SearchFilter,
        rest_filters.OrderingFilter,
    ]
    search_fields = ["phone_number", "full_name", "order_code", "delivery_address"]
    ordering_fields = ["__all__"]

    def get_queryset(self):
        user = self.request.user

        if user.role not in ["YDM_Rider", "YDM_Operator", "YDM_Logistics"]:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You do not have permission to view rider orders.")

        # Get target rider
        if user.role == "YDM_Rider":
            rider = user
        else:
            rider_id = self.request.query_params.get("rider")
            if not rider_id:
                from rest_framework.exceptions import ValidationError

                raise ValidationError({
                    "detail": "rider query parameter (phone number) is required for non-rider users."
                })
            try:
                rider = CustomUser.objects.get(phone_number=rider_id, role="YDM_Rider")
            except CustomUser.DoesNotExist:
                from rest_framework.exceptions import NotFound

                raise NotFound({"detail": "Rider not found or is not a YDM Rider."})

        assigned_order_ids = AssignOrder.objects.filter(user=rider).values_list(
            "order_id", flat=True
        )
        return (
            Order.objects
            .filter(
                id__in=assigned_order_ids,
                logistics__startswith="YDM",
            )
            .select_related("sales_person", "location")
            .prefetch_related(
                "order_products__product__product",
                "assign_orders__user",
                "comments",
                "change_logs",
            )
            .order_by("-id")
        )


class RiderCommissionRateListCreateView(generics.ListCreateAPIView):
    """
    GET  /logistics/rider-commission-rate/  — list all commission rate slabs
    POST /logistics/rider-commission-rate/  — create a new rate slab
    Accessible by: YDM_Operator, YDM_Logistics, Admin
    """

    queryset = RiderCommissionRate.objects.all().order_by("order_min_amount")
    serializer_class = RiderCommissionRateSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        return [IsAuthenticated()]

    def check_permissions(self, request):
        super().check_permissions(request)
        allowed_roles = ["YDM_Operator", "YDM_Logistics", "Admin"]
        if request.user.role not in allowed_roles:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                "Only Operators, Logistics staff, or Admins can manage commission rates."
            )


class RiderCommissionRateRetrieveUpdateDestroyView(
    generics.RetrieveUpdateDestroyAPIView
):
    """
    GET    /logistics/rider-commission-rate/<pk>/  — retrieve a rate slab
    PUT    /logistics/rider-commission-rate/<pk>/  — full update
    PATCH  /logistics/rider-commission-rate/<pk>/  — partial update
    DELETE /logistics/rider-commission-rate/<pk>/  — delete
    Accessible by: YDM_Operator, YDM_Logistics, Admin
    """

    queryset = RiderCommissionRate.objects.all()
    serializer_class = RiderCommissionRateSerializer
    permission_classes = [IsAuthenticated]

    def check_permissions(self, request):
        super().check_permissions(request)
        allowed_roles = ["YDM_Operator", "YDM_Logistics", "Admin"]
        if request.user.role not in allowed_roles:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                "Only Operators, Logistics staff, or Admins can manage commission rates."
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
            OrderChangeLog.objects
            .filter(order_id=OuterRef("pk"), new_status="Sent to YDM")
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

        # Prefetch related data to avoid N+1 queries in the loop
        filtered_qs = filtered_qs.prefetch_related(
            "order_products__product__product", "assign_orders"
        )

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="orders_export.csv"'
        writer = csv.writer(response)

        # --- CSV HEADER ---
        writer.writerow([
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
        ])

        total_product_price = 0
        total_net_amount = 0

        for order in filtered_qs:
            products = order.order_products.all()
            products_str = ", ".join([
                f"{p.quantity}-{p.product.product.name}" for p in products
            ])
            product_price = float(order.total_amount - (order.prepaid_amount or 0))

            # Use rider-set ydm_delivery_charge / ydm_cancelled_charge from AssignOrder; fallback to setting charges
            assignment = next(iter(order.assign_orders.all()), None)
            if order.order_status in [
                "Cancelled",
                "Return Pending",
                "Returned By Customer",
                "Returned By YDM",
            ]:
                if assignment:
                    delivery_charge = float(
                        assignment.ydm_cancelled_charge
                        if assignment.ydm_cancelled_charge is not None
                        else YdmLogisticsSetting.load().cancelled_charge
                    )
                else:
                    delivery_charge = 0.0
            else:
                if assignment and assignment.ydm_delivery_charge is not None:
                    delivery_charge = float(assignment.ydm_delivery_charge)
                else:
                    setting = YdmLogisticsSetting.load()
                    if (
                        assignment
                        and assignment.delivery_location_type == "Outside Ringroad"
                    ):
                        delivery_charge = float(setting.outside_ringroad_charge)
                    else:
                        delivery_charge = float(setting.inside_ringroad_charge)
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

            writer.writerow([
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
            ])

        # --- TOTAL ROW AT THE END ---
        writer.writerow([])
        writer.writerow([
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
        ])

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

            start_date_val = min(
                filter(
                    None,
                    [
                        earliest_order_created,
                        earliest_log_sent,
                        earliest_delivery,
                        earliest_payment,
                    ],
                ),
                default=timezone.now(),
            )
            start_date = (
                start_date_val.date()
                if isinstance(start_date_val, datetime)
                else start_date_val
            )
            end_date = (
                latest_activity.date()
                if isinstance(latest_activity, datetime)
                else latest_activity
            )

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
        return paginator.get_paginated_response({
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
        })


# ---------------- Dashboard Calculation ---------------- #


def calculate_dashboard_pending_cod(franchise_id):
    exclude_status = [
        "Pending",
        "Processing",
        "Sent to Dash",
        "Sent to Daraz",
        "Indrive",
        "Returned By PicknDrop",
        "Sent to PicknDrop",
        "Returned By Dash",
        "Returned By Daraz",
    ]

    assign_order_qs = AssignOrder.objects.filter(
        order__franchise_id=franchise_id,
        order__logistics="YDM",
    )

    filtered_assign_orders = assign_order_qs.exclude(
        order__order_status__in=exclude_status
    )

    total_order = filtered_assign_orders.count()
    total_amount = sum(
        float(ao.order.total_amount or 0) - float(ao.order.prepaid_amount or 0)
        for ao in filtered_assign_orders
    )

    delivered_assign_orders = filtered_assign_orders.filter(
        order__order_status="Delivered"
    )
    delivered_count = delivered_assign_orders.count()
    delivered_amount = sum(
        float(ao.order.total_amount or 0) - float(ao.order.prepaid_amount or 0)
        for ao in delivered_assign_orders
    )

    cancelled_assign_orders = filtered_assign_orders.filter(
        order__order_status__in=[
            "Cancelled",
            "Return Pending",
            "Returned By Customer",
            "Returned By YDM",
        ]
    )
    cancelled_orders = cancelled_assign_orders.count()

    valid_charge = (
        delivered_assign_orders.aggregate(total=Sum("ydm_delivery_charge"))["total"]
        or 0
    )
    cancelled_charge = (
        cancelled_assign_orders.aggregate(total=Sum("ydm_cancelled_charge"))["total"]
        or 0
    )
    total_charge = float(valid_charge) + float(cancelled_charge)

    approved_paid = float(
        Invoice.objects
        .filter(franchise_id=franchise_id, is_approved=True)
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
        Order.objects
        .filter(
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
        Order.objects
        .filter(
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
        Invoice.objects
        .filter(
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
    # Get all delivered orders BEFORE the start_date (same as dashboard logic) using AssignOrder
    pre_start_delivered_agg = AssignOrder.objects.filter(
        order__franchise_id=franchise_id,
        order__logistics="YDM",
        order__order_status="Delivered",
        order__updated_at__date__lt=start_date,
    ).aggregate(
        total=Sum("order__total_amount"),
        prepaid=Sum("order__prepaid_amount"),
    )
    pre_start_delivered_amount = float(
        (pre_start_delivered_agg["total"] or 0)
        - (pre_start_delivered_agg["prepaid"] or 0)
    )

    pre_start_valid_charge = float(
        AssignOrder.objects.filter(
            order__franchise_id=franchise_id,
            order__logistics="YDM",
            order__order_status="Delivered",
            order__updated_at__date__lt=start_date,
        ).aggregate(total=Sum("ydm_delivery_charge"))["total"]
        or 0
    )
    pre_start_cancelled_charge = float(
        AssignOrder.objects.filter(
            order__franchise_id=franchise_id,
            order__logistics="YDM",
            order__order_status__in=[
                "Cancelled",
                "Return Pending",
                "Returned By Customer",
                "Returned By YDM",
            ],
            order__updated_at__date__lt=start_date,
        ).aggregate(total=Sum("ydm_cancelled_charge"))["total"]
        or 0
    )
    pre_start_delivery_charge = pre_start_valid_charge + pre_start_cancelled_charge

    pre_start_payments = float(
        Invoice.objects
        .filter(
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

    # Bulk fetch delivered orders stats in the range grouped by date using AssignOrder
    delivered_orders_in_range = (
        AssignOrder.objects
        .filter(
            order__franchise_id=franchise_id,
            order__logistics="YDM",
            order__order_status="Delivered",
            order__updated_at__date__range=[start_date, end_date],
        )
        .annotate(d_date=TruncDate("order__updated_at"))
        .values("d_date")
        .annotate(
            count=Count("id"),
            total=Sum("order__total_amount"),
            prepaid=Sum("order__prepaid_amount"),
        )
    )
    delivered_stats_by_date = {
        row["d_date"]: {
            "count": row["count"],
            "cash_in": float((row["total"] or 0) - (row["prepaid"] or 0)),
        }
        for row in delivered_orders_in_range
    }

    # Bulk fetch assign orders valid delivery charges in the range grouped by date
    valid_charges_in_range = (
        AssignOrder.objects
        .filter(
            order__franchise_id=franchise_id,
            order__logistics="YDM",
            order__order_status="Delivered",
            order__updated_at__date__range=[start_date, end_date],
        )
        .annotate(d_date=TruncDate("order__updated_at"))
        .values("d_date")
        .annotate(total=Sum("ydm_delivery_charge"))
    )

    # Bulk fetch assign orders cancelled charges in the range grouped by date
    cancelled_charges_in_range = (
        AssignOrder.objects
        .filter(
            order__franchise_id=franchise_id,
            order__logistics="YDM",
            order__order_status__in=[
                "Cancelled",
                "Return Pending",
                "Returned By Customer",
                "Returned By YDM",
            ],
            order__updated_at__date__range=[start_date, end_date],
        )
        .annotate(d_date=TruncDate("order__updated_at"))
        .values("d_date")
        .annotate(total=Sum("ydm_cancelled_charge"))
    )

    charges_by_date = defaultdict(float)
    for row in valid_charges_in_range:
        charges_by_date[row["d_date"]] += float(row["total"] or 0)
    for row in cancelled_charges_in_range:
        charges_by_date[row["d_date"]] += float(row["total"] or 0)

    # For daily calculations, also use Order table instead of logs to avoid duplicates
    for d in sorted(all_dates):
        total_order = len(daily_sent_orders.get(d, []))
        total_amount = sum(daily_sent_orders.get(d, []))

        # Get delivered orders for this date from pre-fetched stats
        del_stats = delivered_stats_by_date.get(d, {"count": 0, "cash_in": 0.0})
        delivery_count = del_stats["count"]
        cash_in = del_stats["cash_in"]

        # Get delivery charge for this date from pre-fetched stats
        delivery_charge = charges_by_date.get(d, 0.0)
        payment = daily_payments.get(d, 0)

        balance_change = cash_in - delivery_charge - payment
        running_balance += balance_change

        statement.append({
            "date": d.strftime("%Y-%m-%d"),
            "total_order": total_order,
            "total_amount": total_amount,
            "delivery_count": delivery_count,
            "cash_in": cash_in,
            "delivery_charge": delivery_charge,
            "payment": payment,
            "balance": round(running_balance, 2),
        })

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
            Order.objects
            .filter(id__in=sent_logs)
            .select_related("franchise", "sales_person", "location")
            .prefetch_related(
                "order_products__product__product", "assign_orders", "change_logs"
            )
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
        writer.writerow([
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
        ])

        total_orders = 0
        total_amount = 0
        total_collection = 0
        total_delivery_charge = 0
        total_net = 0

        for order in orders:
            # Get the exact time when the status change occurred
            target_status = status if status else "Sent to YDM"
            status_log = None
            for log in order.change_logs.all():
                if log.new_status == target_status:
                    status_log = log
                    break

            status_changed_at = (
                status_log.changed_at if status_log else order.created_at
            )

            # Format products string
            products = order.order_products.all()
            products_str = ", ".join([
                f"{p.quantity}-{p.product.product.name}" for p in products
            ])

            # Calculate amounts
            collection_amount = float(order.total_amount or 0) - float(
                order.prepaid_amount or 0
            )
            # Use rider-set ydm_delivery_charge / ydm_cancelled_charge from AssignOrder; fallback to setting charges
            _assignment = next(iter(order.assign_orders.all()), None)
            if order.order_status in [
                "Cancelled",
                "Return Pending",
                "Returned By Customer",
                "Returned By YDM",
            ]:
                if _assignment:
                    delivery_charge = float(
                        _assignment.ydm_cancelled_charge
                        if _assignment.ydm_cancelled_charge is not None
                        else YdmLogisticsSetting.load().cancelled_charge
                    )
                else:
                    delivery_charge = 0.0
            else:
                if _assignment and _assignment.ydm_delivery_charge is not None:
                    delivery_charge = float(_assignment.ydm_delivery_charge)
                else:
                    setting = YdmLogisticsSetting.load()
                    if (
                        _assignment
                        and _assignment.delivery_location_type == "Outside Ringroad"
                    ):
                        delivery_charge = float(setting.outside_ringroad_charge)
                    else:
                        delivery_charge = float(setting.inside_ringroad_charge)
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
            writer.writerow([
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
                status_changed_at.strftime("%Y-%m-%d %H:%M:%S"),  # Status Changed At
                order.remarks or "",  # Remarks
            ])

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


class RiderDailyStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role not in ["YDM_Rider", "YDM_Operator", "YDM_Logistics"]:
            return Response(
                {
                    "detail": "You do not have permission to view rider daily statistics."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get target rider
        if user.role == "YDM_Rider":
            rider = user
        else:
            rider_id = request.query_params.get("rider")
            if not rider_id:
                return Response(
                    {
                        "detail": "rider query parameter (phone number) is required for non-rider users."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                rider = CustomUser.objects.get(phone_number=rider_id, role="YDM_Rider")
            except CustomUser.DoesNotExist:
                return Response(
                    {"detail": "Rider not found or is not a YDM Rider."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")

        start_date = None
        end_date = None

        if not start_date_str and not end_date_str:
            today = timezone.localdate()
            start_date = today.replace(day=1)
            end_date = today
        else:
            try:
                if start_date_str:
                    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                if end_date_str:
                    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {
                        "detail": "Invalid date format. Use YYYY-MM-DD for start_date and end_date."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Get change log querysets filtered by rider assignment
        delivered_logs = OrderChangeLog.objects.filter(
            order__assign_orders__user=rider,
            new_status="Delivered",
        )

        return_statuses = [
            "Cancelled",
            "Returned By Customer",
            "Returned By YDM",
            "Return Pending",
        ]
        returned_logs = OrderChangeLog.objects.filter(
            order__assign_orders__user=rider,
            new_status__in=return_statuses,
        )

        if start_date:
            delivered_logs = delivered_logs.filter(changed_at__date__gte=start_date)
            returned_logs = returned_logs.filter(changed_at__date__gte=start_date)
        if end_date:
            delivered_logs = delivered_logs.filter(changed_at__date__lte=end_date)
            returned_logs = returned_logs.filter(changed_at__date__lte=end_date)

        # Group by date and count unique order_ids
        delivered_counts = (
            delivered_logs
            .annotate(date=TruncDate("changed_at"))
            .values("date")
            .annotate(count=Count("order_id", distinct=True))
            .values_list("date", "count")
        )
        delivered_map = {row[0]: row[1] for row in delivered_counts}

        returned_counts = (
            returned_logs
            .annotate(date=TruncDate("changed_at"))
            .values("date")
            .annotate(count=Count("order_id", distinct=True))
            .values_list("date", "count")
        )
        returned_map = {row[0]: row[1] for row in returned_counts}

        # Build combined list of daily counts
        all_dates = sorted(
            set(delivered_map.keys()) | set(returned_map.keys()), reverse=True
        )

        results = []
        for d in all_dates:
            results.append({
                "date": d.strftime("%Y-%m-%d") if d else None,
                "delivered_count": delivered_map.get(d, 0),
                "returned_count": returned_map.get(d, 0),
            })

        return Response(results, status=status.HTTP_200_OK)


class YdmLogisticsSettingView(APIView):
    """
    GET   /logistics/settings/  — retrieve the singleton setting (auto-creates with defaults if missing)
    POST  /logistics/settings/  — create or update the singleton setting (upsert)
    PUT   /logistics/settings/  — full update
    PATCH /logistics/settings/  — partial update
    Accessible by: YDM_Operator, YDM_Logistics, SuperAdmin
    """

    permission_classes = [IsAuthenticated]
    allowed_roles = ["YDM_Operator", "YDM_Logistics", "SuperAdmin"]

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.user.role not in self.allowed_roles:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                "Only Operators, Logistics staff, or Admins can manage logistics settings."
            )

    def get(self, request):
        setting = YdmLogisticsSetting.load()
        serializer = YdmLogisticsSettingSerializer(setting)
        return Response(serializer.data)

    def post(self, request):
        # Upsert: create if not exists, update if already exists
        setting = YdmLogisticsSetting.load()
        serializer = YdmLogisticsSettingSerializer(
            setting, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        setting = YdmLogisticsSetting.load()
        serializer = YdmLogisticsSettingSerializer(
            setting, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

