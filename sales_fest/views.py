from datetime import datetime

from django.db.models import Sum
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sales.models import Order, OrderProduct
from sales.serializers import TopSalespersonSerializer

from .models import FestConfig, SalesGroup
from .serializers import (
    FestConfigSerializer,
    SalesGroupSerializer,
    SalesGroupSerializer2,
)


class SalesGroupListCreateView(generics.ListCreateAPIView):
    queryset = SalesGroup.objects.all().order_by("-created_at")
    serializer_class = SalesGroupSerializer

    def get_serializer_class(self):
        if self.request.method == "GET":
            return SalesGroupSerializer2
        return SalesGroupSerializer

    def perform_create(self, serializer):
        user = self.request.user
        group = serializer.save()

        # Get or create fest-config for the user's franchise
        fest_config, created = FestConfig.objects.get_or_create(
            franchise=user.franchise
        )

        fest_config.sales_group.add(group)
        if fest_config.has_sales_fest is False:
            fest_config.has_sales_fest = True
            fest_config.save()


class SalesGroupDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = SalesGroup.objects.all()
    serializer_class = SalesGroupSerializer


class FestConfigListCreateView(generics.ListCreateAPIView):
    queryset = FestConfig.objects.all()
    serializer_class = FestConfigSerializer

    def get(self, request, *args, **kwargs):
        user = self.request.user
        fest_config = FestConfig.objects.filter(franchise=user.franchise)
        if fest_config.exists():
            return self.list(request, *args, **kwargs)
        else:
            FestConfig.objects.create(franchise=user.franchise)
            return self.list(request, *args, **kwargs)

    def perform_create(self, serializer):
        user = self.request.user
        # Default to existing franchise if not a Franchise user or missing attribute
        franchise = getattr(serializer.instance, "franchise", None)
        if getattr(user, "role", None) == "Franchise":
            franchise = getattr(user, "franchise", franchise)

        serializer.save(franchise=franchise)


class FestConfigRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = FestConfig.objects.all()
    serializer_class = FestConfigSerializer
    lookup_field = "franchise_id"

    def get_object(self):
        franchise_id = self.kwargs.get("franchise_id")
        # Try to get or create FestConfig for this franchise_id
        obj, created = FestConfig.objects.get_or_create(franchise_id=franchise_id)
        return obj

    def perform_update(self, serializer):
        # Get the current instance before updating
        instance = self.get_object()
        franchise_id = instance.franchise_id

        # Check if has_sales_fest is being set to False
        if (
            serializer.validated_data.get("has_sales_fest") is False
            and instance.has_sales_fest
        ):
            # Delete all associated sales groups
            instance.sales_group.all().delete()
        if serializer.validated_data.get("has_lucky_draw") is False:
            if instance.lucky_draw_system is not None:
                instance.lucky_draw_system = None
            # Remove lucky_draw_system from validated_data to prevent serializer overwrite
            serializer.validated_data.pop("lucky_draw_system", None)

        # Save serializer
        serializer.save(franchise_id=franchise_id)


class SalesGroupStatsView(generics.ListAPIView):
    serializer_class = TopSalespersonSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        # Get user's franchise - all users should have a franchise for this to work
        if not user.franchise:
            return SalesGroup.objects.none()

        # Get the fest config for user's franchise
        try:
            fest_config = FestConfig.objects.get(franchise=user.franchise)
            if not fest_config.has_sales_fest:
                return SalesGroup.objects.none()
        except FestConfig.DoesNotExist:
            return SalesGroup.objects.none()

        # Return sales groups from the fest config
        return fest_config.sales_group.all()

    def list(self, request, *args, **kwargs):
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

        # Get sales groups
        sales_groups = self.get_queryset()

        if not sales_groups.exists():
            return Response(
                {
                    "filter_type": filter_type,
                    "results": [],
                    "message": "No sales groups found or sales fest not enabled",
                }
            )

        # Initialize orders_filter for date filtering
        orders_filter = {}

        # Handle date filtering
        if specific_date and not end_date:
            try:
                specific_date_obj = datetime.strptime(specific_date, "%Y-%m-%d").date()
                orders_filter["date"] = specific_date_obj
            except ValueError:
                return Response(
                    {"error": "Invalid date format. Use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif specific_date and end_date:
            try:
                specific_date_obj = datetime.strptime(specific_date, "%Y-%m-%d").date()
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
                orders_filter["date__gte"] = specific_date_obj
                orders_filter["date__lte"] = end_date_obj
            except ValueError:
                return Response(
                    {"error": "Invalid date format. Use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif filter_type == "daily":
            orders_filter["date"] = current_date.date()
        elif filter_type == "weekly":
            orders_filter["date__gte"] = current_date.date() - timezone.timedelta(
                days=7
            )
        elif filter_type == "monthly":
            orders_filter["date__year"] = current_date.year
            orders_filter["date__month"] = current_date.month

        results = []

        for sales_group in sales_groups:
            group_data = {
                "group_name": sales_group.group_name,
                "leader": sales_group.leader.get_full_name()
                if sales_group.leader
                else None,
                "total_sales": 0,
                "sales_count": 0,
                "total_members": 0,
                "members": [],
                "sales_members": [],
            }

            # Get all members of this sales group
            members = sales_group.members.filter(role="SalesPerson")
            group_data["total_members"] = members.count()

            for member in members:
                # Get orders for this member with date and status filters
                orders_query = Order.objects.filter(
                    sales_person=member, **orders_filter
                ).exclude(order_status__in=excluded_statuses)

                # Calculate member's sales data
                member_sales_count = orders_query.count()
                member_total_sales = (
                    orders_query.aggregate(total=Sum("total_amount"))["total"] or 0
                )

                # Get product sales for this member
                product_sales = (
                    OrderProduct.objects.filter(order__in=orders_query)
                    .values("product__product__id", "product__product__name")
                    .annotate(total_quantity=Sum("quantity"))
                    .order_by("-total_quantity")
                )

                member_data = {
                    "salesperson_name": member.get_full_name(),
                    "salesperson_id": member.id,
                    "total_sales": float(member_total_sales),
                    "sales_count": member_sales_count,
                    "product_sales": [
                        {
                            "product_name": p["product__product__name"],
                            "quantity": p["total_quantity"],
                        }
                        for p in product_sales
                    ],
                }

                # Add to group totals
                group_data["total_sales"] += member_total_sales
                group_data["sales_count"] += member_sales_count

                # Only add members who have sales data
                if member_sales_count > 0:
                    group_data["members"].append(member_data)
                # Add to no sales members list
                group_data["sales_members"].append(member.get_full_name())

            # Convert group total sales to float
            group_data["total_sales"] = float(group_data["total_sales"])

            # Sort members by total sales (descending)
            group_data["members"].sort(key=lambda x: x["total_sales"], reverse=True)

            # Always add groups (even if no sales)
            results.append(group_data)

        # Sort groups by total sales (descending)
        results.sort(key=lambda x: x["total_sales"], reverse=True)

        response_data = {
            "results": results,
            "total_groups": len(results),
        }

        return Response(response_data)
