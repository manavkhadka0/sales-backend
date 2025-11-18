from datetime import datetime

from django.db import models
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth, TruncWeek, TruncYear
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from account.models import CustomUser, Franchise
from sales.models import Inventory, Order, OrderProduct
from sales.serializers import (
    OrderSerializer,
    SalesPersonStatisticsSerializer,
    TopSalespersonSerializer,
)

# Create your views here.


class LatestOrdersView(generics.ListAPIView):
    queryset = Order.objects.order_by("-id")[:5]  # Get the latest 5 orders
    serializer_class = OrderSerializer


class SalesStatisticsView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get_stats_for_queryset(self, queryset, today):
        """Helper method to get statistics for a queryset"""
        # Define excluded statuses
        excluded_statuses = [
            "Cancelled",
            "Returned By Customer",
            "Returned By Dash",
            "Returned By YDM",
            "Return Pending",
            "Returned By PicknDrop",
        ]

        # Calculate yesterday's date
        yesterday = today - timezone.timedelta(days=1)

        # Get today's stats - no exclusions
        daily_stats = (
            queryset.filter(date=today)
            .exclude(order_status__in=excluded_statuses)
            .aggregate(total_orders=Count("id"), total_sales=Sum("total_amount"))
        )

        # Get yesterday's stats - no exclusions
        yesterday_stats = (
            queryset.filter(date=yesterday)
            .exclude(order_status__in=excluded_statuses)
            .aggregate(total_orders=Count("id"), total_sales=Sum("total_amount"))
        )

        # Get all-time stats with status breakdown
        all_time_stats = queryset.aggregate(
            # Active orders and sales
            all_time_orders=Count("id", filter=~Q(order_status__in=excluded_statuses)),
            all_time_sales=Sum(
                "total_amount", filter=~Q(order_status__in=excluded_statuses), default=0
            ),
            # Cancelled orders and sales totals
            cancelled_orders_count=Count(
                "id", filter=Q(order_status__in=excluded_statuses)
            ),
            all_time_cancelled_sales=Sum(
                "total_amount", filter=Q(order_status__in=excluded_statuses), default=0
            ),
            # Status-specific counts for active orders
            pending_count=Count("id", filter=Q(order_status="Pending")),
            processing_count=Count("id", filter=Q(order_status="Processing")),
            sent_to_dash_count=Count("id", filter=Q(order_status="Sent to Dash")),
            delivered_count=Count("id", filter=Q(order_status="Delivered")),
            indrive_count=Count("id", filter=Q(order_status="Indrive")),
            # Status-specific counts and amounts for cancelled orders
            cancelled_count=Count("id", filter=Q(order_status="Cancelled")),
            cancelled_amount=Sum(
                "total_amount", filter=Q(order_status="Cancelled"), default=0
            ),
            returned_by_customer_count=Count(
                "id", filter=Q(order_status="Returned By Customer")
            ),
            returned_by_customer_amount=Sum(
                "total_amount", filter=Q(order_status="Returned By Customer"), default=0
            ),
            returned_by_dash_count=Count(
                "id", filter=Q(order_status="Returned By Dash")
            ),
            returned_by_dash_amount=Sum(
                "total_amount", filter=Q(order_status="Returned By Dash"), default=0
            ),
            returned_by_pickndrop_count=Count(
                "id", filter=Q(order_status="Returned By PicknDrop")
            ),
            returned_by_pickndrop_amount=Sum(
                "total_amount",
                filter=Q(order_status="Returned By PicknDrop"),
                default=0,
            ),
            return_pending_count=Count("id", filter=Q(order_status="Return Pending")),
            return_pending_amount=Sum(
                "total_amount", filter=Q(order_status="Return Pending"), default=0
            ),
        )

        return {
            "date": today,
            "total_orders": daily_stats["total_orders"] or 0,
            "total_sales": daily_stats["total_sales"] or 0,
            "total_orders_yesterday": yesterday_stats["total_orders"] or 0,
            "total_sales_yesterday": yesterday_stats["total_sales"] or 0,
            "all_time_orders": all_time_stats["all_time_orders"] or 0,
            "cancelled_orders_count": all_time_stats["cancelled_orders_count"] or 0,
            "cancelled_orders": {
                "cancelled": all_time_stats["cancelled_count"] or 0,
                "returned_by_customer": all_time_stats["returned_by_customer_count"]
                or 0,
                "returned_by_dash": all_time_stats["returned_by_dash_count"] or 0,
                "return_pending": all_time_stats["return_pending_count"] or 0,
                "returned_by_pickndrop": all_time_stats["returned_by_pickndrop_count"]
                or 0,
            },
            "all_time_sales": float(all_time_stats["all_time_sales"] or 0),
            "all_time_cancelled_sales": float(
                all_time_stats["all_time_cancelled_sales"] or 0
            ),
            "cancelled_amount": {
                "cancelled": float(all_time_stats["cancelled_amount"] or 0),
                "returned_by_customer": float(
                    all_time_stats["returned_by_customer_amount"] or 0
                ),
                "returned_by_dash": float(
                    all_time_stats["returned_by_dash_amount"] or 0
                ),
                "return_pending": float(all_time_stats["return_pending_amount"] or 0),
                "returned_by_pickndrop": float(
                    all_time_stats["returned_by_pickndrop_amount"] or 0
                ),
            },
        }

    def get(self, request):
        franchise = self.request.query_params.get("franchise")
        distributor = self.request.query_params.get("distributor")
        user = self.request.user
        today = timezone.now().date()

        if user.role == "SuperAdmin":
            if franchise:
                queryset = Order.objects.filter(franchise=franchise)
            elif distributor:
                queryset = Order.objects.filter(distributor=distributor)
            else:
                queryset = Order.objects.filter(factory=user.factory)
        elif user.role == "Distributor":
            franchises = Franchise.objects.filter(distributor=user.distributor)
            queryset = Order.objects.filter(franchise__in=franchises)
        elif user.role in ["Franchise", "Packaging"]:
            queryset = Order.objects.filter(franchise=user.franchise)
        elif user.role == "SalesPerson":
            queryset = Order.objects.filter(sales_person=user)
        else:
            return Response(
                {"detail": "You don't have permission to view statistics"},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(self.get_stats_for_queryset(queryset, today))


class TopSalespersonView(generics.ListAPIView):
    serializer_class = TopSalespersonSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        franchise = self.request.query_params.get("franchise")
        distributor = self.request.query_params.get("distributor")
        user = self.request.user
        filter_type = self.request.GET.get("filter", "daily")
        specific_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        current_date = timezone.now()

        # Define excluded statuses
        excluded_statuses = [
            "Cancelled",
            "Returned By Customer",
            "Returned By Dash",
            "Return Pending",
            "Returned By PicknDrop",
            "Returned By YDM",
        ]

        if user.role == "SuperAdmin":
            if franchise:
                salespersons = CustomUser.objects.filter(
                    role="SalesPerson", franchise=franchise
                )
            elif distributor:
                salespersons = CustomUser.objects.filter(
                    role="SalesPerson", distributor=distributor
                )
            else:
                salespersons = CustomUser.objects.filter(
                    factory=user.factory, role="SalesPerson"
                )
        elif user.role == "Distributor":
            franchises = Franchise.objects.filter(distributor=user.distributor)
            salespersons = CustomUser.objects.filter(
                role="SalesPerson", franchise__in=franchises
            )
        elif user.role in ["Franchise", "SalesPerson", "Packaging"]:
            salespersons = CustomUser.objects.filter(
                role="SalesPerson", franchise=user.franchise
            )
        else:
            return CustomUser.objects.none()

        # Initialize orders_filter
        orders_filter = {}

        # Handle date filtering
        if specific_date and not end_date:
            try:
                specific_date = datetime.strptime(specific_date, "%Y-%m-%d").date()
                orders_filter["orders__date"] = specific_date
            except ValueError:
                return CustomUser.objects.none()
        elif specific_date and end_date:
            try:
                specific_date = datetime.strptime(specific_date, "%Y-%m-%d").date()
                end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
                orders_filter["orders__date__gte"] = specific_date
                orders_filter["orders__date__lte"] = end_date
            except ValueError:
                return CustomUser.objects.none()
        elif filter_type:
            if filter_type == "daily":
                start_date = current_date.date()
                orders_filter["orders__date"] = start_date
            elif filter_type == "weekly":
                start_date = current_date - timezone.timedelta(days=7)
                orders_filter["orders__date__gte"] = start_date
            elif filter_type == "monthly":
                orders_filter["orders__date__year"] = current_date.year
                orders_filter["orders__date__month"] = current_date.month

        # Create base queryset with time filters
        salespersons = (
            salespersons.annotate(
                sales_count=Count(
                    "orders",
                    filter=models.Q(**orders_filter)
                    & ~models.Q(orders__order_status__in=excluded_statuses),
                ),
                total_sales=Sum(
                    "orders__total_amount",
                    filter=models.Q(**orders_filter)
                    & ~models.Q(orders__order_status__in=excluded_statuses),
                ),
            )
            .filter(sales_count__gt=0, total_sales__gt=0)
            .order_by("-sales_count", "-total_sales")
        )

        return salespersons

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data

        filter_type = request.GET.get("filter", "daily")
        specific_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        current_date = timezone.now()

        # Define excluded statuses
        excluded_statuses = [
            "Cancelled",
            "Returned By Customer",
            "Returned By Dash",
            "Return Pending",
            "Returned By PicknDrop",
            "Returned By YDM",
        ]

        for index, item in enumerate(data):
            salesperson = queryset[index]

            orders_query = Order.objects.filter(sales_person=salesperson).exclude(
                order_status__in=excluded_statuses
            )

            # Apply date filtering
            if specific_date and not end_date:
                try:
                    # Convert string to date object
                    specific_date_obj = datetime.strptime(
                        specific_date, "%Y-%m-%d"
                    ).date()
                    orders_query = orders_query.filter(date=specific_date_obj)
                except ValueError:
                    return Response(
                        {"error": "Invalid date format. Use YYYY-MM-DD"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            elif specific_date and end_date:
                try:
                    # Convert strings to date objects
                    specific_date_obj = datetime.strptime(
                        specific_date, "%Y-%m-%d"
                    ).date()
                    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
                    orders_query = orders_query.filter(
                        date__gte=specific_date_obj, date__lte=end_date_obj
                    )
                except ValueError:
                    return Response(
                        {"error": "Invalid date format. Use YYYY-MM-DD"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            elif filter_type == "daily":
                orders_query = orders_query.filter(date=current_date.date())
            elif filter_type == "weekly":
                orders_query = orders_query.filter(
                    date__gte=current_date - timezone.timedelta(days=7)
                )
            elif filter_type == "monthly":
                orders_query = orders_query.filter(
                    date__year=current_date.year, date__month=current_date.month
                )

            product_sales = (
                OrderProduct.objects.filter(order__in=orders_query)
                .values("product__product__id", "product__product__name")
                .annotate(total_quantity=Sum("quantity"))
                .order_by("-total_quantity")
            )

            item["sales_count"] = queryset[index].sales_count
            item["total_sales"] = float(queryset[index].total_sales)
            item["product_sales"] = [
                {
                    "product_name": p["product__product__name"],
                    "quantity_sold": p["total_quantity"],
                }
                for p in product_sales
            ]

        response_data = {"filter_type": filter_type, "results": data}

        return Response(response_data)


class RevenueView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        franchise = self.request.query_params.get("franchise")
        distributor = self.request.query_params.get("distributor")
        user = self.request.user
        filter_type = request.GET.get("filter", "monthly")  # Default to monthly
        today = timezone.now().date()

        # Define excluded statuses
        excluded_statuses = [
            "Cancelled",
            "Returned By Customer",
            "Returned By Dash",
            "Return Pending",
            "Returned By PicknDrop",
            "Returned By YDM",
        ]

        try:
            # Base queryset based on user role
            if user.role == "SuperAdmin":
                if franchise:
                    base_queryset = Order.objects.filter(franchise=franchise)
                elif distributor:
                    base_queryset = Order.objects.filter(distributor=distributor)
                else:
                    base_queryset = Order.objects.filter(factory=user.factory)
            elif user.role == "Distributor":
                franchises = Franchise.objects.filter(distributor=user.distributor)
                base_queryset = Order.objects.filter(franchise__in=franchises)
            elif user.role in ["Franchise", "Packaging"]:
                base_queryset = Order.objects.filter(franchise=user.franchise)
            elif user.role == "SalesPerson":
                base_queryset = Order.objects.filter(sales_person=user)
            else:
                return Response(
                    {"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN
                )
            base_queryset = base_queryset.exclude(order_status__in=excluded_statuses)

            if filter_type == "daily":
                revenue = (
                    base_queryset.filter(
                        created_at__year=today.year, created_at__month=today.month
                    )
                    .values("date")
                    .annotate(
                        period=models.F("date"),
                        total_revenue=Sum("total_amount", default=0),
                        order_count=Count("id"),
                    )
                    .order_by("date")
                )

            elif filter_type == "weekly":
                revenue = (
                    base_queryset.filter(created_at__year=today.year)
                    .annotate(period=TruncWeek("created_at"))
                    .values("period")
                    .annotate(
                        total_revenue=Sum("total_amount", default=0),
                        order_count=Count("id"),
                    )
                    .order_by("period")
                )

            elif filter_type == "yearly":
                revenue = (
                    base_queryset.annotate(period=TruncYear("created_at"))
                    .values("period")
                    .annotate(
                        total_revenue=Sum("total_amount", default=0),
                        order_count=Count("id"),
                    )
                    .order_by("period")
                )

            else:  # Default is monthly
                revenue = (
                    base_queryset.annotate(period=TruncMonth("created_at"))
                    .values("period")
                    .annotate(
                        total_revenue=Sum("total_amount", default=0),
                        order_count=Count("id"),
                    )
                    .order_by("period")
                )

            # Format the response data
            response_data = [
                {
                    "period": entry["period"].strftime("%Y-%m-%d")
                    if filter_type == "daily"
                    else entry["period"].strftime(
                        "%Y-%m-%d"
                        if filter_type == "weekly"
                        else "%Y-%m"
                        if filter_type == "monthly"
                        else "%Y"
                    ),
                    "total_revenue": float(entry["total_revenue"]),
                    "order_count": entry["order_count"],
                }
                for entry in revenue
            ]

            return Response(
                {
                    "filter_type": filter_type,
                    "user_role": user.role,
                    "data": response_data,
                }
            )

        except Exception as e:
            return Response(
                {"error": f"Failed to fetch revenue data: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class RevenueWithCancelledView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        franchise = self.request.query_params.get("franchise")
        distributor = self.request.query_params.get("distributor")
        user = self.request.user
        filter_type = request.GET.get("filter", "daily")  # Default to daily
        specific_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        today = timezone.now().date()

        # Define active order statuses
        excluded_statuses = [
            "Cancelled",
            "Returned By Customer",
            "Returned By Dash",
            "Return Pending",
            "Returned By PicknDrop",
            "Returned By YDM",
        ]

        try:
            # Base queryset based on user role
            if user.role == "SuperAdmin":
                if franchise:
                    base_queryset = Order.objects.filter(franchise=franchise)
                elif distributor:
                    base_queryset = Order.objects.filter(distributor=distributor)
                else:
                    base_queryset = Order.objects.filter(factory=user.factory)
            elif user.role == "Distributor":
                franchises = Franchise.objects.filter(distributor=user.distributor)
                base_queryset = Order.objects.filter(franchise__in=franchises)
            elif user.role in ["Franchise", "Packaging"]:
                base_queryset = Order.objects.filter(franchise=user.franchise)
            elif user.role == "SalesPerson":
                base_queryset = Order.objects.filter(sales_person=user)
            else:
                return Response(
                    {"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN
                )

            # Common annotation fields with status-specific counts
            annotation_fields = {
                "total_revenue": Sum("total_amount", default=0),
                "total_cancelled_amount": Sum(
                    "total_amount",
                    filter=Q(order_status__in=excluded_statuses),
                    default=0,
                ),
                "order_count": Count("id"),
                "cancelled_count": Count(
                    "id", filter=Q(order_status__in=excluded_statuses)
                ),
                # Status-specific counts for active orders
                "pending_count": Count("id", filter=Q(order_status="Pending")),
                "processing_count": Count("id", filter=Q(order_status="Processing")),
                "sent_to_dash_count": Count(
                    "id", filter=Q(order_status="Sent to Dash")
                ),
                "delivered_count": Count("id", filter=Q(order_status="Delivered")),
                "indrive_count": Count("id", filter=Q(order_status="Indrive")),
                # Status-specific counts for cancelled orders
                "cancelled_status_count": Count(
                    "id", filter=Q(order_status="Cancelled")
                ),
                "returned_by_customer_count": Count(
                    "id", filter=Q(order_status="Returned By Customer")
                ),
                "returned_by_dash_count": Count(
                    "id", filter=Q(order_status="Returned By Dash")
                ),
                "return_pending_count": Count(
                    "id", filter=Q(order_status="Return Pending")
                ),
                "returned_by_pickndrop_count": Count(
                    "id", filter=Q(order_status="Returned By PicknDrop")
                ),
                "returned_by_ydm_count": Count(
                    "id", filter=Q(order_status="Returned By YDM")
                ),
            }

            # Handle date filtering
            if specific_date and not end_date:
                try:
                    # Convert string to date object
                    specific_date_obj = datetime.strptime(
                        specific_date, "%Y-%m-%d"
                    ).date()
                    base_queryset = base_queryset.filter(date=specific_date_obj)
                    revenue = (
                        base_queryset.values("date")
                        .annotate(period=models.F("date"), **annotation_fields)
                        .order_by("date")
                    )
                except ValueError:
                    return Response(
                        {"error": "Invalid date format. Use YYYY-MM-DD"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            elif specific_date and end_date:
                try:
                    # Convert strings to date objects
                    specific_date_obj = datetime.strptime(
                        specific_date, "%Y-%m-%d"
                    ).date()
                    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
                    base_queryset = base_queryset.filter(
                        date__gte=specific_date_obj, date__lte=end_date_obj
                    )
                    revenue = (
                        base_queryset.values("date")
                        .annotate(period=models.F("date"), **annotation_fields)
                        .order_by("date")
                    )
                except ValueError:
                    return Response(
                        {"error": "Invalid date format. Use YYYY-MM-DD"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                # Handle filter types
                if filter_type == "daily":
                    revenue = (
                        base_queryset.filter(
                            date__year=today.year, date__month=today.month
                        )
                        .values("date")
                        .annotate(period=models.F("date"), **annotation_fields)
                        .order_by("date")
                    )
                elif filter_type == "weekly":
                    revenue = (
                        base_queryset.filter(date__year=today.year)
                        .annotate(period=TruncWeek("date"))
                        .values("period")
                        .annotate(**annotation_fields)
                        .order_by("period")
                    )
                elif filter_type == "monthly":
                    revenue = (
                        base_queryset.annotate(period=TruncMonth("date"))
                        .values("period")
                        .annotate(**annotation_fields)
                        .order_by("period")
                    )
                elif filter_type == "yearly":
                    revenue = (
                        base_queryset.annotate(period=TruncYear("date"))
                        .values("period")
                        .annotate(**annotation_fields)
                        .order_by("period")
                    )

            # Format response data with detailed status counts
            response_data = [
                {
                    "period": entry["period"].strftime(
                        "%Y-%m-%d"
                        if filter_type in ["daily", "weekly"]
                        or (specific_date or end_date)
                        else "%Y-%m"
                        if filter_type == "monthly"
                        else "%Y"
                    ),
                    "total_revenue": float(entry["total_revenue"]),
                    "total_cancelled_amount": float(entry["total_cancelled_amount"]),
                    "order_count": entry["order_count"],
                    "cancelled_count": entry["cancelled_count"],
                    "active_orders": {
                        "pending": entry["pending_count"],
                        "processing": entry["processing_count"],
                        "sent_to_dash": entry["sent_to_dash_count"],
                        "delivered": entry["delivered_count"],
                        "indrive": entry["indrive_count"],
                    },
                    "cancelled_orders": {
                        "cancelled": entry["cancelled_status_count"],
                        "returned_by_customer": entry["returned_by_customer_count"],
                        "returned_by_dash": entry["returned_by_dash_count"],
                        "return_pending": entry["return_pending_count"],
                    },
                }
                for entry in revenue
            ]

            return Response({"filter_type": filter_type, "data": response_data})

        except Exception as e:
            return Response(
                {"error": f"Failed to fetch revenue data: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class TopProductsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            franchise = self.request.query_params.get("franchise")
            distributor = self.request.query_params.get("distributor")
            user = self.request.user
            filter_type = request.GET.get("filter")
            current_date = timezone.now()

            # Define excluded statuses
            excluded_statuses = [
                "Cancelled",
                "Returned By Customer",
                "Returned By Dash",
                "Return Pending",
                "Returned By PicknDrop",
                "Returned By YDM",
            ]

            # Base query for order products based on user role
            if user.role == "SuperAdmin":
                if franchise:
                    base_query = OrderProduct.objects.filter(
                        order__franchise=franchise,
                        order__order_status__in=[
                            "Delivered",
                            "Pending",
                            "Indrive",
                            "Sent to Dash",
                            "Processing",
                        ],
                    ).exclude(order__order_status__in=excluded_statuses)
                elif distributor:
                    base_query = OrderProduct.objects.filter(
                        order__distributor=distributor,
                        order__order_status__in=[
                            "Delivered",
                            "Pending",
                            "Indrive",
                            "Sent to Dash",
                            "Processing",
                        ],
                    ).exclude(order__order_status__in=excluded_statuses)
                else:
                    base_query = OrderProduct.objects.filter(
                        order__factory=user.factory,
                        order__order_status__in=[
                            "Delivered",
                            "Pending",
                            "Indrive",
                            "Sent to Dash",
                            "Processing",
                        ],
                    ).exclude(order__order_status__in=excluded_statuses)
            elif user.role == "Distributor":
                franchises = Franchise.objects.filter(distributor=user.distributor)
                base_query = OrderProduct.objects.filter(
                    order__franchise__in=franchises,
                    order__order_status__in=[
                        "Delivered",
                        "Pending",
                        "Indrive",
                        "Sent to Dash",
                        "Processing",
                    ],
                ).exclude(order__order_status__in=excluded_statuses)
            elif user.role in ["Franchise", "Packaging"]:
                base_query = OrderProduct.objects.filter(
                    order__franchise=user.franchise,
                    order__order_status__in=[
                        "Delivered",
                        "Pending",
                        "Indrive",
                        "Sent to Dash",
                        "Processing",
                    ],
                ).exclude(order__order_status__in=excluded_statuses)
            elif user.role == "SalesPerson":
                base_query = OrderProduct.objects.filter(
                    order__sales_person=user,
                    order__order_status__in=[
                        "Delivered",
                        "Pending",
                        "Indrive",
                        "Sent to Dash",
                        "Processing",
                    ],
                ).exclude(order__order_status__in=excluded_statuses)
            else:
                return Response(
                    {"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN
                )

            # Apply time filter if specified
            if filter_type:
                if filter_type == "weekly":
                    # Filter for the last 7 days
                    start_date = current_date - timezone.timedelta(days=7)
                    base_query = base_query.filter(order__created_at__gte=start_date)
                elif filter_type == "monthly":
                    # Filter for current month only
                    base_query = base_query.filter(
                        order__created_at__year=current_date.year,
                        order__created_at__month=current_date.month,
                    )

            # Get top products with aggregated data
            top_products = (
                base_query.values("product__product__id", "product__product__name")
                .annotate(
                    total_quantity=Sum("quantity"),
                    total_amount=Sum(
                        models.F("quantity")
                        * models.F("order__total_amount")
                        / models.Subquery(
                            OrderProduct.objects.filter(order=models.OuterRef("order"))
                            .values("order")
                            .annotate(total_qty=Sum("quantity"))
                            .values("total_qty")[:1]
                        )
                    ),
                )
                .order_by("-total_quantity")  # Get top 5 by quantity
            )

            # Calculate total revenue
            total_revenue = sum(item["total_amount"] for item in top_products)

            # Format the response with percentages
            product_data = []
            for item in top_products:
                product_data.append(
                    {
                        "product_id": item["product__product__id"],
                        "product_name": item["product__product__name"],
                        "total_quantity": item["total_quantity"],
                        "total_amount": round(float(item["total_amount"]), 2)
                        if item["total_amount"]
                        else 0.0,
                    }
                )

            # Sort by revenue percentage in descending order
            product_data.sort(key=lambda x: x["total_amount"], reverse=True)

            response_data = {
                "total_revenue": round(float(total_revenue), 2),
                "products": product_data,
                "revenue_distribution": {
                    "labels": [item["product_name"] for item in product_data],
                    "percentages": [item["total_amount"] for item in product_data],
                },
            }

            return Response(response_data)

        except Exception as e:
            return Response(
                {"error": f"Failed to fetch top products data: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class DashboardStatsView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        franchise = request.GET.get("franchise")
        distributor = request.GET.get("distributor")
        user = self.request.user
        current_date = timezone.now()
        last_month = current_date - timezone.timedelta(days=30)

        # Define excluded statuses
        excluded_statuses = [
            "Cancelled",
            "Returned By Customer",
            "Returned By Dash",
            "Return Pending",
            "Returned By PicknDrop",
            "Returned By YDM",
        ]

        # Base queryset filters based on user role
        if user.role == "SuperAdmin":
            if franchise:
                orders = Order.objects.filter(franchise=franchise)
            elif distributor:
                orders = Order.objects.filter(distributor=distributor)
            else:
                orders = Order.objects.filter(factory=user.factory)
            # For SuperAdmin: all orders, all distributors/franchises as customers, all products
            customers = CustomUser.objects.filter(
                role__in=["Distributor", "Franchise", "SalesPerson"], is_active=True
            )
            products = (
                Inventory.objects.filter(
                    factory=user.factory, status="ready_to_dispatch"
                )
                .values("product")
                .distinct()
            )

        elif user.role == "Distributor":
            # For Distributor: orders from their franchises, their franchises as customers
            franchises = Franchise.objects.filter(distributor=user.distributor)
            orders = Order.objects.filter(franchise__in=franchises)
            customers = CustomUser.objects.filter(
                franchise__in=franchises, is_active=True
            )
            products = (
                Inventory.objects.filter(
                    distributor=user.distributor, status="ready_to_dispatch"
                )
                .values("product")
                .distinct()
            )

        elif user.role in ["Franchise", "SalesPerson", "Packaging"]:
            # For Franchise/SalesPerson: their orders, their sales persons as customers
            orders = Order.objects.filter(franchise=user.franchise)
            customers = CustomUser.objects.filter(
                franchise=user.franchise, role="SalesPerson", is_active=True
            )
            products = (
                Inventory.objects.filter(
                    franchise=user.franchise, status="ready_to_dispatch"
                )
                .values("product")
                .distinct()
            )
        else:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        # Calculate current period stats
        current_revenue = (
            orders.filter(
                created_at__gte=last_month,
                order_status__in=[
                    "Delivered",
                    "Pending",
                    "Indrive",
                    "Processing",
                    "Sent to Dash",
                ],
            )
            .exclude(order_status__in=excluded_statuses)
            .aggregate(total=Sum("total_amount"))["total"]
            or 0
        )

        current_orders = (
            orders.filter(created_at__gte=last_month)
            .exclude(order_status__in=excluded_statuses)
            .count()
        )
        current_customers = customers.filter(date_joined__gte=last_month).count()
        current_products = products.count()

        # Calculate previous period stats for comparison
        previous_month = last_month - timezone.timedelta(days=30)
        previous_revenue = (
            orders.filter(
                created_at__gte=previous_month,
                created_at__lt=last_month,
                order_status__in=[
                    "Delivered",
                    "Pending",
                    "Indrive",
                    "Processing",
                    "Sent to Dash",
                ],
            )
            .exclude(order_status__in=excluded_statuses)
            .aggregate(total=Sum("total_amount"))["total"]
            or 0
        )

        previous_orders = (
            orders.filter(
                created_at__gte=previous_month,
                created_at__lt=last_month,
                order_status__in=[
                    "Delivered",
                    "Pending",
                    "Indrive",
                    "Processing",
                    "Sent to Dash",
                ],
            )
            .exclude(order_status__in=excluded_statuses)
            .count()
        )

        previous_customers = customers.filter(
            date_joined__gte=previous_month, date_joined__lt=last_month
        ).count()

        previous_products = (
            Inventory.objects.filter(
                created_at__gte=previous_month, created_at__lt=last_month
            )
            .values("product")
            .distinct()
            .count()
        )

        # Calculate percentage changes
        def calculate_percentage_change(current, previous):
            if previous == 0:
                return 100 if current > 0 else 0
            return ((current - previous) / previous) * 100

        revenue_change = calculate_percentage_change(current_revenue, previous_revenue)
        orders_change = calculate_percentage_change(current_orders, previous_orders)
        customers_change = calculate_percentage_change(
            current_customers, previous_customers
        )
        products_change = calculate_percentage_change(
            current_products, previous_products
        )

        response_data = {
            "total_revenue": {
                "amount": float(current_revenue),
                "percentage_change": round(revenue_change, 1),
                "change_label": "from last month",
            },
            "orders": {
                "count": current_orders,
                "percentage_change": round(orders_change, 1),
                "change_label": "from last month",
            },
            "customers": {
                "count": current_customers,
                "percentage_change": round(customers_change, 1),
                "change_label": "from last month",
            },
            "active_products": {
                "count": current_products,
                "percentage_change": round(products_change, 1),
                "change_label": "from last month",
            },
        }

        return Response(response_data)


class RevenueByProductView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        franchise = request.GET.get("franchise")
        distributor = request.GET.get("distributor")
        user = self.request.user
        # Get filter parameter from query
        filter_type = request.GET.get("filter")
        current_date = timezone.now()

        # Define excluded statuses
        excluded_statuses = [
            "Cancelled",
            "Returned By Customer",
            "Returned By Dash",
            "Return Pending",
            "Returned By PicknDrop",
            "Returned By YDM",
        ]

        # Filter orders based on user role
        if user.role == "SuperAdmin":
            if franchise:
                orders = Order.objects.filter(franchise=franchise)
            elif distributor:
                orders = Order.objects.filter(distributor=distributor)
            else:
                orders = Order.objects.filter(
                    order_status__in=[
                        "Delivered",
                        "Pending",
                        "Indrive",
                        "Sent to Dash",
                        "Processing",
                    ]
                ).exclude(order_status__in=excluded_statuses)
        elif user.role == "Distributor":
            franchises = Franchise.objects.filter(distributor=user.distributor)
            orders = Order.objects.filter(
                franchise__in=franchises,
                order_status__in=[
                    "Delivered",
                    "Pending",
                    "Indrive",
                    "Sent to Dash",
                    "Processing",
                ],
            ).exclude(order_status__in=excluded_statuses)
        elif user.role in ["Franchise", "SalesPerson", "Packaging"]:
            orders = Order.objects.filter(
                franchise=user.franchise,
                order_status__in=[
                    "Delivered",
                    "Pending",
                    "Indrive",
                    "Sent to Dash",
                    "Processing",
                ],
            ).exclude(order_status__in=excluded_statuses)
        else:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        # Apply time filter if specified
        if filter_type:
            if filter_type == "weekly":
                # Filter for the last 7 days
                start_date = current_date - timezone.timedelta(days=7)
                orders = orders.filter(created_at__gte=start_date)
            elif filter_type == "monthly":
                # Filter for current month only
                orders = orders.filter(
                    created_at__year=current_date.year,
                    created_at__month=current_date.month,
                )

        # Get all order products and calculate revenue per product
        product_revenue = (
            OrderProduct.objects.filter(order__in=orders)
            .values("product__product__id", "product__product__name")
            .annotate(
                total_revenue=Sum(
                    models.F("quantity")
                    * models.F("order__total_amount")
                    / models.Subquery(
                        OrderProduct.objects.filter(order=models.OuterRef("order"))
                        .values("order")
                        .annotate(total_qty=Sum("quantity"))
                        .values("total_qty")[:1]
                    )
                )
            )
            .order_by("-total_revenue")
        )

        # Calculate total revenue
        total_revenue = sum(item["total_revenue"] for item in product_revenue)

        # Format the response with percentages
        product_data = []
        for item in product_revenue:
            percentage = (
                (item["total_revenue"] / total_revenue * 100)
                if total_revenue > 0
                else 0
            )
            product_data.append(
                {
                    "product_id": item["product__product__id"],
                    "product_name": item["product__product__name"],
                    "revenue": round(float(item["total_revenue"]), 2),
                    "percentage": round(percentage, 1),
                }
            )

        # Sort by revenue percentage in descending order
        product_data.sort(key=lambda x: x["percentage"], reverse=True)

        response_data = {
            "total_revenue": round(float(total_revenue), 2),
            "products": product_data,
            "revenue_distribution": {
                "labels": [item["product_name"] for item in product_data],
                "percentages": [item["percentage"] for item in product_data],
            },
        }

        return Response(response_data)


class SalesPersonStatisticsView(APIView):
    def get(self, request, phone_number):
        excluded_statuses = [
            "Cancelled",
            "Returned By Customer",
            "Returned By Dash",
            "Return Pending",
            "Returned By PicknDrop",
            "Returned By YDM",
        ]

        try:
            # Get the salesperson
            salesperson = CustomUser.objects.get(phone_number=phone_number)

            # Check if the user is a salesperson
            if salesperson.role != "SalesPerson":
                return Response(
                    {"error": "User is not a salesperson"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Get filter type and specific date from query params
            filter_type = request.query_params.get("filter", "all")
            specific_date = request.query_params.get("date")
            end_date = request.query_params.get("end_date")

            # Base queryset for orders
            orders = Order.objects.filter(sales_person=salesperson)

            # Apply specific date filter if provided
            if specific_date and not end_date:
                try:
                    specific_date = datetime.strptime(specific_date, "%Y-%m-%d").date()
                    orders = orders.filter(created_at__date=specific_date)
                except ValueError:
                    return Response(
                        {"error": "Invalid date format. Use YYYY-MM-DD"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            elif specific_date and end_date:
                try:
                    specific_date = datetime.strptime(specific_date, "%Y-%m-%d").date()
                    end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
                    orders = orders.filter(
                        created_at__date__gte=specific_date,
                        created_at__date__lte=end_date,
                    )
                except ValueError:
                    return Response(
                        {"error": "Invalid date format. Use YYYY-MM-DD"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            # Apply time filter if no specific date is provided
            elif filter_type == "daily":
                orders = orders.filter(created_at__date=timezone.now().date())
            elif filter_type == "weekly":
                orders = orders.filter(
                    created_at__gte=timezone.now() - timezone.timedelta(days=7)
                )
            elif filter_type == "monthly":
                orders = orders.filter(
                    created_at__gte=timezone.now() - timezone.timedelta(days=30)
                )

            # Calculate total orders and amount
            total_orders = orders.exclude(order_status__in=excluded_statuses).count()
            total_cancelled_orders = orders.filter(
                order_status__in=excluded_statuses
            ).count()
            total_amount = (
                orders.exclude(order_status__in=excluded_statuses).aggregate(
                    total=Sum("total_amount")
                )["total"]
                or 0
            )
            total_cancelled_amount = (
                orders.filter(order_status__in=excluded_statuses).aggregate(
                    total=Sum("total_amount")
                )["total"]
                or 0
            )
            total_delivery_charge = (
                orders.exclude(order_status__in=excluded_statuses).aggregate(
                    total=Sum("delivery_charge")
                )["total"]
                or 0
            )
            total_cancelled_delivery_charge = (
                orders.filter(order_status__in=excluded_statuses).aggregate(
                    total=Sum("delivery_charge")
                )["total"]
                or 0
            )

            # Get product-wise sales data
            product_sales = (
                OrderProduct.objects.filter(
                    order__in=orders.exclude(order_status__in=excluded_statuses)
                )
                .values("product__product__id", "product__product__name")
                .annotate(quantity_sold=Sum("quantity"))
                .order_by("-quantity_sold")
            )

            # Get product-wise sales data for cancelled orders
            cancelled_product_sales = (
                OrderProduct.objects.filter(
                    order__in=orders.filter(order_status__in=excluded_statuses)
                )
                .values("product__product__id", "product__product__name")
                .annotate(quantity_sold=Sum("quantity"))
                .order_by("-quantity_sold")
            )

            # Prepare response data
            data = {
                "user": salesperson,
                "total_orders": total_orders,
                "total_amount": float(total_amount),
                "total_cancelled_orders": total_cancelled_orders,
                "total_cancelled_amount": float(total_cancelled_amount),
                "total_delivery_charge": float(total_delivery_charge),
                "total_cancelled_delivery_charge": float(
                    total_cancelled_delivery_charge
                ),
                "product_sales": [
                    {
                        "product_name": p["product__product__name"],
                        "quantity_sold": p["quantity_sold"],
                    }
                    for p in product_sales
                ],
                "cancelled_product_sales": [
                    {
                        "product_name": p["product__product__name"],
                        "quantity_sold": p["quantity_sold"],
                    }
                    for p in cancelled_product_sales
                ],
            }

            serializer = SalesPersonStatisticsSerializer(data)
            return Response(serializer.data)

        except CustomUser.DoesNotExist:
            return Response(
                {"error": "Salesperson not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SalesPersonRevenueView(generics.GenericAPIView):
    def get(self, request, phone_number):
        excluded_statuses = [
            "Cancelled",
            "Returned By Customer",
            "Returned By Dash",
            "Return Pending",
            "Returned By PicknDrop",
            "Returned By YDM",
        ]
        try:
            salesperson = CustomUser.objects.get(phone_number=phone_number)
            if salesperson.role != "SalesPerson":
                return Response(
                    {"error": "User is not a salesperson"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            filter_type = request.query_params.get("filter", "daily")
            specific_date = request.query_params.get("date")
            end_date = request.query_params.get("end_date")
            today = timezone.now().date()

            # Base queryset for the specific salesperson
            base_queryset = Order.objects.filter(sales_person=salesperson)

            # Common annotation fields with status-specific counts
            annotation_fields = {
                "total_revenue": Sum("total_amount", default=0),
                "total_cancelled_amount": Sum(
                    "total_amount",
                    filter=Q(order_status__in=excluded_statuses),
                    default=0,
                ),
                "order_count": Count("id"),
                "cancelled_count": Count(
                    "id", filter=Q(order_status__in=excluded_statuses)
                ),
                # Status-specific counts for active orders
                "pending_count": Count("id", filter=Q(order_status="Pending")),
                "processing_count": Count("id", filter=Q(order_status="Processing")),
                "sent_to_dash_count": Count(
                    "id", filter=Q(order_status="Sent to Dash")
                ),
                "delivered_count": Count("id", filter=Q(order_status="Delivered")),
                "indrive_count": Count("id", filter=Q(order_status="Indrive")),
                # Status-specific counts for cancelled orders
                "cancelled_status_count": Count(
                    "id", filter=Q(order_status="Cancelled")
                ),
                "returned_by_customer_count": Count(
                    "id", filter=Q(order_status="Returned By Customer")
                ),
                "returned_by_dash_count": Count(
                    "id", filter=Q(order_status="Returned By Dash")
                ),
                "return_pending_count": Count(
                    "id", filter=Q(order_status="Return Pending")
                ),
                "returned_by_pickndrop_count": Count(
                    "id", filter=Q(order_status="Returned By PicknDrop")
                ),
                "returned_by_ydm_count": Count(
                    "id", filter=Q(order_status="Returned By YDM")
                ),
            }

            # Handle date range queries
            if specific_date:
                try:
                    # Convert string to date object
                    specific_date = datetime.strptime(specific_date, "%Y-%m-%d").date()
                    if end_date:
                        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
                        date_filter = {
                            "created_at__date__range": (specific_date, end_date)
                        }
                    else:
                        date_filter = {"created_at__date": specific_date}

                    revenue = (
                        base_queryset.filter(**date_filter)
                        .values("created_at__date")
                        .annotate(
                            period=models.F("created_at__date"), **annotation_fields
                        )
                        .order_by("created_at__date")
                    )
                except ValueError:
                    return Response(
                        {"error": "Invalid date format. Use YYYY-MM-DD"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                # Handle filter types
                if filter_type == "daily":
                    revenue = (
                        base_queryset.filter(
                            created_at__year=today.year, created_at__month=today.month
                        )
                        .values("date")
                        .annotate(period=models.F("date"), **annotation_fields)
                        .order_by("date")
                    )
                elif filter_type == "weekly":
                    revenue = (
                        base_queryset.filter(created_at__year=today.year)
                        .annotate(period=TruncWeek("created_at"))
                        .values("period")
                        .annotate(**annotation_fields)
                        .order_by("period")
                    )
                elif filter_type == "monthly":
                    revenue = (
                        base_queryset.annotate(period=TruncMonth("created_at"))
                        .values("period")
                        .annotate(**annotation_fields)
                        .order_by("period")
                    )
                elif filter_type == "yearly":
                    revenue = (
                        base_queryset.annotate(period=TruncYear("created_at"))
                        .values("period")
                        .annotate(**annotation_fields)
                        .order_by("period")
                    )

            # Format response data with detailed status counts
            response_data = [
                {
                    "period": entry["period"].strftime(
                        "%Y-%m-%d"
                        if filter_type in ["daily", "weekly"] or specific_date
                        else "%Y-%m"
                        if filter_type == "monthly"
                        else "%Y"
                    ),
                    "total_revenue": float(entry["total_revenue"]),
                    "total_cancelled_amount": float(entry["total_cancelled_amount"]),
                    "order_count": entry["order_count"],
                    "cancelled_count": entry["cancelled_count"],
                    "active_orders": {
                        "pending": entry["pending_count"],
                        "processing": entry["processing_count"],
                        "sent_to_dash": entry["sent_to_dash_count"],
                        "delivered": entry["delivered_count"],
                        "indrive": entry["indrive_count"],
                    },
                    "cancelled_orders": {
                        "cancelled": entry["cancelled_status_count"],
                        "returned_by_customer": entry["returned_by_customer_count"],
                        "returned_by_dash": entry["returned_by_dash_count"],
                        "return_pending": entry["return_pending_count"],
                        "returned_by_pickndrop": entry["returned_by_pickndrop_count"],
                        "returned_by_ydm": entry["returned_by_ydm_count"],
                    },
                }
                for entry in revenue
            ]

            return Response(
                {
                    "filter_type": filter_type,
                    "specific_date": specific_date.strftime("%Y-%m-%d")
                    if specific_date
                    else None,
                    "data": response_data,
                }
            )

        except CustomUser.DoesNotExist:
            return Response(
                {"error": "Salesperson not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to fetch revenue data: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class BulkOrdersView(generics.ListAPIView):
    """
    View to show daily bulk orders (orders with >3 hairoil products) for this month
    with date range filter and product quantities.

    Query Parameters:
    - start_date: Start date for filtering (YYYY-MM-DD format)
    - end_date: End date for filtering (YYYY-MM-DD format)
    - product_keywords: Keywords to identify hairoil products (default: 'hair,oil')

    Usage Examples:
    - GET /api/bulk-orders/  # This month's bulk orders
    - GET /api/bulk-orders/?start_date=2024-01-01&end_date=2024-01-31
    - GET /api/bulk-orders/?product_keywords=hair,oil
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        product_keywords = request.query_params.get("product_keywords", "oil bottle")

        # Parse dates
        today = timezone.now().date()
        current_month_start = today.replace(day=1)

        if start_date:
            try:
                start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Invalid start_date format. Use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            start_date = current_month_start

        if end_date:
            try:
                end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Invalid end_date format. Use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            # Default to end of current month
            next_month = today.replace(day=28) + timezone.timedelta(days=4)
            end_date = next_month - timezone.timedelta(days=next_month.day)

        # Get base queryset based on user role
        queryset = self._get_user_orders_queryset(user)

        if not queryset:
            return Response(
                {"error": "No orders found for your role"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Filter by date range
        queryset = queryset.filter(date__gte=start_date, date__lte=end_date)

        # Get bulk orders (orders with >3 hairoil products)
        bulk_orders = self._get_bulk_orders(queryset, product_keywords)

        # Group by date and aggregate product quantities
        daily_bulk_orders = self._aggregate_bulk_orders_by_date(bulk_orders)

        return Response(
            {
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "total_bulk_orders": len(bulk_orders),
                "daily_breakdown": daily_bulk_orders,
            }
        )

    def _get_user_orders_queryset(self, user):
        """Get orders queryset based on user role"""
        if user.role == "SuperAdmin":
            return Order.objects.filter(factory=user.factory)
        elif user.role == "Distributor":
            franchises = Franchise.objects.filter(distributor=user.distributor)
            return Order.objects.filter(franchise__in=franchises)
        elif user.role in ["Franchise", "Packaging"]:
            return Order.objects.filter(franchise=user.franchise)
        elif user.role == "SalesPerson":
            return Order.objects.filter(sales_person=user)
        else:
            return None

    def _get_bulk_orders(self, queryset, product_keywords):
        """Filter orders that have >3 total quantity of products matching keywords"""
        from django.db.models import Q, Sum

        # Split keywords and create filter conditions (similar to filter_oil_bottle_total_min)
        keywords_list = [kw.strip().lower() for kw in product_keywords.split(",")]

        # Create Q objects for all keywords (OR condition)
        keyword_filters = Q()
        for keyword in keywords_list:
            keyword_filters |= Q(
                order_products__product__product__name__icontains=keyword
            )

        # Annotate orders with total quantity of matching products (same as filter_oil_bottle_total_min)
        annotated_orders = queryset.annotate(
            matching_products_qty=Sum(
                "order_products__quantity", filter=keyword_filters
            )
        )

        # Filter for bulk orders (total quantity >= 3)
        bulk_orders = annotated_orders.filter(matching_products_qty__gte=3)
        return bulk_orders

    def _aggregate_bulk_orders_by_date(self, bulk_orders):
        """Group bulk orders by date and aggregate product quantities"""
        from collections import defaultdict

        daily_data = defaultdict(lambda: defaultdict(int))
        daily_order_counts = defaultdict(int)

        for order in bulk_orders:
            order_date = order.date.strftime("%Y-%m-%d")
            order_products = OrderProduct.objects.filter(order=order)

            # Count bulk orders per date
            daily_order_counts[order_date] += 1

            for order_product in order_products:
                product_name = order_product.product.product.name
                quantity = order_product.quantity

                # Only include oil bottle products in the aggregation
                if self._is_oil_bottle_product(product_name):
                    # Add to daily totals
                    daily_data[order_date][product_name] += quantity

        # Convert to sorted list format - only include dates with actual bulk orders
        result = []
        for date in sorted(daily_data.keys()):
            products_data = []
            for product_name, total_quantity in daily_data[date].items():
                products_data.append(
                    {"product_name": product_name, "total_quantity": total_quantity}
                )

            # Only include dates where there are oil bottle products (bulk orders exist)
            if products_data:
                result.append(
                    {
                        "date": date,
                        "bulk_orders_count": daily_order_counts[date],
                        "products": products_data,
                    }
                )

        return result

    def _is_oil_bottle_product(self, product_name):
        """Check if a product name contains oil bottle keywords"""
        oil_keywords = [
            "oil bottle",
            "oil",
        ]  # More specific - only oil-related products
        product_name_lower = product_name.lower()

        # Check if any oil bottle keyword is in the product name
        for keyword in oil_keywords:
            if keyword in product_name_lower:
                return True
        return False
