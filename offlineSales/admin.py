from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from offlineSales.models import (
    Attendance,
    AttendanceConfig,
    OfflineCustomer,
    OfflineOrder,
    OfflineOrderItem,
    OfflinePaymentHistory,
)


class OfflineOrderItemInline(TabularInline):
    model = OfflineOrderItem
    extra = 0
    fields = ("inventory", "quantity")
    raw_id_fields = ("inventory",)


class OfflinePaymentHistoryInline(TabularInline):
    model = OfflinePaymentHistory
    extra = 0
    fields = (
        "amount",
        "payment_method",
        "payment_screenshot",
        "remarks",
        "recorded_by",
        "payment_date",
    )
    readonly_fields = ("payment_date",)
    raw_id_fields = ("recorded_by",)


@admin.register(OfflineCustomer)
class OfflineCustomerAdmin(ModelAdmin):
    list_display = (
        "store_name",
        "contact_person",
        "phone_number",
        "franchise",
        "sales_person",
        "total_orders_count",
        "total_purchased_amount",
        "total_paid_amount",
        "total_remaining_amount",
        "is_active",
        "created_at",
    )
    list_filter = ("franchise", "is_active", "created_at")
    search_fields = ("store_name", "contact_person", "phone_number", "address")
    raw_id_fields = ("franchise", "sales_person")
    inlines = [OfflinePaymentHistoryInline]


@admin.register(OfflineOrder)
class OfflineOrderAdmin(ModelAdmin):
    list_display = (
        "customer",
        "order_code",
        "franchise",
        "sales_person",
        "order_date",
        "order_status",
        "payment_status",
        "total_amount",
        "paid_amount",
        "remaining_amount",
        "created_at",
    )
    list_filter = ("franchise", "order_status", "payment_status", "order_date")
    search_fields = (
        "order_code",
        "customer__store_name",
        "customer__contact_person",
        "customer__phone_number",
    )
    raw_id_fields = ("customer", "franchise", "sales_person")
    inlines = [OfflineOrderItemInline, OfflinePaymentHistoryInline]


@admin.register(OfflinePaymentHistory)
class OfflinePaymentHistoryAdmin(ModelAdmin):
    list_display = (
        "customer",
        "order",
        "amount",
        "payment_method",
        "recorded_by",
        "payment_date",
    )
    list_filter = ("payment_method", "payment_date")
    search_fields = (
        "order__order_code",
        "customer__store_name",
        "customer__phone_number",
        "order__customer__store_name",
        "order__customer__phone_number",
        "remarks",
    )
    raw_id_fields = ("customer", "order", "recorded_by")


@admin.register(AttendanceConfig)
class AttendanceConfigAdmin(ModelAdmin):
    list_display = ("cutoff_time", "updated_by", "updated_at")
    readonly_fields = ("updated_by", "updated_at", "created_at")

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    def has_add_permission(self, request):
        # Singleton: block creating a second row from admin
        return not AttendanceConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Attendance)
class AttendanceAdmin(ModelAdmin):
    list_display = (
        "sales_person",
        "attendance_date",
        "attendance_time",
        "attendance_location",
    )
    list_filter = ("attendance_date",)
    search_fields = (
        "sales_person__username",
        "sales_person__first_name",
        "sales_person__last_name",
    )
    raw_id_fields = ("sales_person",)
    readonly_fields = ("attendance_date", "attendance_time")
