from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from offlineSales.models import (
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
