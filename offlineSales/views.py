from django.db.models import Q
from django.http import Http404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from offlineSales.filters import (
    AttendanceFilter,
    OfflineCustomerFilter,
    OfflineOrderCreditReminderFilter,
    OfflineOrderFilter,
    OfflinePaymentHistoryFilter,
    OfflineSalesAccessFilter,
)
from offlineSales.models import Attendance, AttendanceConfig
from offlineSales.permissions import CanPostAttendance, CanViewAttendance, IsSuperAdmin
from offlineSales.selectors.access_selector import get_offline_sales_access_queryset
from offlineSales.selectors.attendance_selector import get_attendance_queryset
from offlineSales.selectors.customer_selector import get_customer_queryset
from offlineSales.selectors.order_selector import (
    get_customer_orders,
    get_order_queryset,
    get_pending_credit_reminders,
)
from offlineSales.selectors.payment_selector import get_payment_queryset
from offlineSales.selectors.stats_selector import get_offline_sales_stats
from offlineSales.serializers import (
    AttendanceConfigSerializer,
    AttendanceConfigUpdateSerializer,
    AttendanceCreateSerializer,
    AttendanceSerializer,
    OfflineCustomerSerializer,
    OfflineOrderCreateSerializer,
    OfflineOrderCreditReminderSerializer,
    OfflineOrderDetailSerializer,
    OfflineOrderListSerializer,
    OfflinePaymentHistorySerializer,
    OfflineSalesAccessCreateSerializer,
    OfflineSalesAccessSerializer,
    OfflineSalesStatsSerializer,
    RecordPaymentCreateSerializer,
)
from offlineSales.services.attendance_service import update_attendance_config
from offlineSales.services.order_service import cancel_offline_order
from sales.views import CustomPagination


class OfflineCustomerListCreateView(generics.ListCreateAPIView):
    """
    List registered offline store customers (with credit & sales summaries)
    or register a new retail customer.
    """

    serializer_class = OfflineCustomerSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = (
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    )
    filterset_class = OfflineCustomerFilter
    pagination_class = CustomPagination
    search_fields = ["store_name", "contact_person", "phone_number", "address"]
    ordering_fields = [
        "created_at",
        "store_name",
        "annotated_total_remaining",
        "annotated_total_purchased",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        return get_customer_queryset(self.request.user)

    def perform_create(self, serializer):
        user = self.request.user
        franchise = user.franchise if hasattr(user, "franchise") else None
        serializer.save(
            franchise=franchise
            if not serializer.validated_data.get("franchise")
            else serializer.validated_data.get("franchise"),
            sales_person=user
            if not serializer.validated_data.get("sales_person")
            else serializer.validated_data.get("sales_person"),
        )


class OfflineCustomerDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or soft-disable a retail customer.
    """

    serializer_class = OfflineCustomerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_customer_queryset(self.request.user)


class OfflineOrderListCreateView(generics.ListCreateAPIView):
    """
    List offline sales orders (with order & payment statuses)
    or place a new offline order with store customers.
    """

    permission_classes = [IsAuthenticated]
    filter_backends = (
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    )
    filterset_class = OfflineOrderFilter
    pagination_class = CustomPagination
    search_fields = [
        "order_code",
        "customer__store_name",
        "customer__contact_person",
        "customer__phone_number",
    ]
    ordering_fields = [
        "created_at",
        "order_date",
        "total_amount",
        "paid_amount",
        "remaining_amount",
    ]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return OfflineOrderCreateSerializer
        return OfflineOrderListSerializer

    def get_queryset(self):
        return get_order_queryset(self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        output_serializer = OfflineOrderDetailSerializer(
            order, context=self.get_serializer_context()
        )
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class OfflineOrderDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve or update an offline sales order details, items, and payment history using order_code.
    Cancelling the order via update (order_status='Cancelled') or DELETE restores the deducted inventory.
    """

    serializer_class = OfflineOrderDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "order_code"
    lookup_url_kwarg = "order_code"

    def get_queryset(self):
        return get_order_queryset(self.request.user)

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        lookup_value = self.kwargs.get(self.lookup_url_kwarg or self.lookup_field)

        if str(lookup_value).isdigit():
            obj = queryset.filter(
                Q(order_code=lookup_value) | Q(id=int(lookup_value))
            ).first()
        else:
            obj = queryset.filter(order_code=lookup_value).first()

        if not obj:
            raise Http404(f"No OfflineOrder found with order_code '{lookup_value}'.")

        self.check_object_permissions(self.request, obj)
        return obj

    def destroy(self, request, *args, **kwargs):
        order = self.get_object()
        cancelled_order = cancel_offline_order(order, request.user)
        output_serializer = self.get_serializer(cancelled_order)
        return Response(
            {
                "message": "Order successfully cancelled and inventory stock restored.",
                "data": output_serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class OfflineCustomerOrdersListView(generics.ListAPIView):
    """
    Retrieve all offline sales orders placed for a specific customer/store.
    """

    serializer_class = OfflineOrderListSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = (
        DjangoFilterBackend,
        filters.OrderingFilter,
    )
    filterset_class = OfflineOrderFilter
    pagination_class = CustomPagination
    ordering = ["-created_at"]

    def get_queryset(self):
        customer_id = self.kwargs.get("customer_id")
        return get_customer_orders(customer_id, self.request.user)


class OfflinePaymentHistoryListCreateView(generics.ListCreateAPIView):
    """
    List payment records across orders or record a new incremental payment
    against a customer credit order.
    """

    permission_classes = [IsAuthenticated]
    filter_backends = (
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    )
    filterset_class = OfflinePaymentHistoryFilter
    pagination_class = CustomPagination
    search_fields = [
        "order__order_code",
        "order__customer__store_name",
        "order__customer__phone_number",
    ]
    ordering_fields = ["payment_date", "amount", "created_at"]
    ordering = ["-payment_date"]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return RecordPaymentCreateSerializer
        return OfflinePaymentHistorySerializer

    def get_queryset(self):
        return get_payment_queryset(self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()
        output_serializer = OfflinePaymentHistorySerializer(
            payment, context=self.get_serializer_context()
        )
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class OfflinePaymentHistoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete an offline payment history record.
    """

    serializer_class = OfflinePaymentHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_payment_queryset(self.request.user)


class OfflineOrderCancelView(generics.GenericAPIView):
    """
    Cancel an offline order using order_code and automatically restore the deducted inventory.
    """

    permission_classes = [IsAuthenticated]
    lookup_field = "order_code"
    lookup_url_kwarg = "order_code"

    def get_queryset(self):
        return get_order_queryset(self.request.user)

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        lookup_value = self.kwargs.get(self.lookup_url_kwarg or self.lookup_field)

        if str(lookup_value).isdigit():
            obj = queryset.filter(
                Q(order_code=lookup_value) | Q(id=int(lookup_value))
            ).first()
        else:
            obj = queryset.filter(order_code=lookup_value).first()

        if not obj:
            raise Http404(f"No OfflineOrder found with order_code '{lookup_value}'.")

        self.check_object_permissions(self.request, obj)
        return obj

    def post(self, request, *args, **kwargs):
        order = self.get_object()
        cancelled_order = cancel_offline_order(order, request.user)
        output_serializer = OfflineOrderDetailSerializer(
            cancelled_order, context={"request": request}
        )
        return Response(
            {
                "message": "Order successfully cancelled and inventory stock restored.",
                "data": output_serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class OfflineOrderCreditReminderListView(generics.ListAPIView):
    """
    List orders with pending credit close to or past the 3-month (90 days) credit window.
    Ordered by oldest order_date first to highlight urgent credit collections.
    """

    serializer_class = OfflineOrderCreditReminderSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = (
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    )
    filterset_class = OfflineOrderCreditReminderFilter
    search_fields = [
        "order_code",
        "customer__store_name",
        "customer__contact_person",
        "customer__phone_number",
    ]
    ordering_fields = ["order_date", "remaining_amount", "created_at"]
    ordering = ["order_date"]

    def get_queryset(self):
        return get_pending_credit_reminders(self.request.user)


class OfflineSalesStatsView(generics.GenericAPIView):
    """
    Retrieve overall statistics for offline sales:
    - total_customers
    - customers_with_pending_credit
    - total_orders
    - pending_orders_count
    - close_to_due_orders_count (approaching 3 months)
    - overdue_orders_count (past 3 months)
    - total_order_amount
    - total_paid_amountg
    - total_remaining_amount
    """

    serializer_class = OfflineSalesStatsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        stats = get_offline_sales_stats(request.user)
        serializer = self.get_serializer(stats)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Attendance Config Views
# ---------------------------------------------------------------------------


class AttendanceConfigView(generics.GenericAPIView):
    """
    GET  → Any authenticated user can read the current config.
    PATCH → Only SuperAdmin can update cutoff_time and is_active.
    """

    def get_permissions(self):
        if self.request.method in ("PATCH", "PUT"):
            return [IsSuperAdmin()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return AttendanceConfigUpdateSerializer
        return AttendanceConfigSerializer

    def get_object(self):
        return AttendanceConfig.get_config()

    def get(self, request, *args, **kwargs):
        config = self.get_object()
        serializer = AttendanceConfigSerializer(config)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, *args, **kwargs):
        config = self.get_object()
        serializer = AttendanceConfigUpdateSerializer(
            config, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        updated_config = update_attendance_config(
            config, serializer.validated_data, request.user
        )
        return Response(
            AttendanceConfigSerializer(updated_config).data,
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Attendance Views
# ---------------------------------------------------------------------------


class AttendanceListCreateView(generics.ListCreateAPIView):
    """
    GET  → List attendance records (scoped by role: own records for salespersons,
           all/franchise-filtered records for supervisors).
    POST → Salespersons post today's attendance (validated against cutoff time).
    """

    pagination_class = CustomPagination
    filter_backends = (
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    )
    filterset_class = AttendanceFilter
    search_fields = [
        "sales_person__username",
        "sales_person__first_name",
        "sales_person__last_name",
    ]
    ordering_fields = ["attendance_date", "attendance_time"]
    ordering = ["-attendance_date"]

    def get_permissions(self):
        if self.request.method == "POST":
            return [CanPostAttendance()]
        return [CanViewAttendance()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AttendanceCreateSerializer
        return AttendanceSerializer

    def get_queryset(self):
        return get_attendance_queryset(self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        attendance = serializer.save()
        output_serializer = AttendanceSerializer(attendance)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class AttendanceDetailView(generics.RetrieveAPIView):
    """
    Retrieve a single attendance record.
    Salespersons can only access their own; supervisors can access all.
    """

    serializer_class = AttendanceSerializer
    permission_classes = [CanViewAttendance]

    def get_queryset(self):
        return get_attendance_queryset(self.request.user)


class AttendanceTodayCheckView(generics.GenericAPIView):
    """
    Check whether the requesting salesperson has already posted attendance today.
    Returns: { "attendance": true | false }
    """

    permission_classes = [CanPostAttendance]

    def get(self, request, *args, **kwargs):
        today = timezone.localdate()
        has_attendance = Attendance.objects.filter(
            sales_person=request.user,
            attendance_date=today,
        ).exists()
        return Response({"attendance": has_attendance}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Offline Sales Access Views
# ---------------------------------------------------------------------------


class OfflineSalesAccessListCreateView(generics.ListCreateAPIView):
    """
    List users who have been granted offline sales access or grant access to a user.
    """

    pagination_class = CustomPagination
    filter_backends = (
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    )
    filterset_class = OfflineSalesAccessFilter
    search_fields = [
        "user__username",
        "user__first_name",
        "user__last_name",
        "user__email",
        "user__phone_number",
    ]
    ordering_fields = ["granted_at", "user__first_name", "user__username"]
    ordering = ["-granted_at"]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsSuperAdmin()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return OfflineSalesAccessCreateSerializer
        return OfflineSalesAccessSerializer

    def get_queryset(self):
        return get_offline_sales_access_queryset()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        access = serializer.save()
        output_serializer = OfflineSalesAccessSerializer(
            access, context=self.get_serializer_context()
        )
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class OfflineSalesAccessDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or revoke offline sales access for a user.
    """

    serializer_class = OfflineSalesAccessSerializer

    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH", "DELETE"):
            return [IsSuperAdmin()]
        return [AllowAny()]

    def get_queryset(self):
        return get_offline_sales_access_queryset()
