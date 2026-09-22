from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import CustomerTreatment, Image, PaymentHistory


class ImageInline(TabularInline):
    model = Image
    extra = 1
    fields = ("day_number", "image", "created_at")
    readonly_fields = ("created_at",)


class PaymentHistoryInline(TabularInline):
    model = PaymentHistory
    extra = 1
    fields = (
        "amount",
        "payment_method",
        "payment_screenshot",
        "remarks",
        "created_by",
        "payment_date",
    )
    readonly_fields = ("payment_date",)
    raw_id_fields = ("created_by",)


@admin.register(CustomerTreatment)
class CustomerTreatmentAdmin(ModelAdmin):
    list_display = (
        "name",
        "phone_number",
        "treatment_type",
        "package",
        "total_amount",
        "paid_amount",
        "payment_method",
        "reason",
        "franchise",
        "calculated_total_amount",
        "total_paid",
        "due_amount",
        "payment_status",
        "service_by",
        "created_at",
    )
    list_filter = ("treatment_type", "package", "payment_method", "franchise", "created_at")
    search_fields = ("name", "phone_number", "address", "reason")
    raw_id_fields = ("service_by", "franchise")
    inlines = [ImageInline, PaymentHistoryInline]


@admin.register(Image)
class ImageAdmin(ModelAdmin):
    list_display = ("id", "customer_treatment", "day_number", "created_at")
    list_filter = ("day_number", "created_at")
    search_fields = ("customer_treatment__name", "customer_treatment__phone_number")


@admin.register(PaymentHistory)
class PaymentHistoryAdmin(ModelAdmin):
    list_display = (
        "customer_treatment",
        "amount",
        "payment_method",
        "created_by",
        "payment_date",
    )
    list_filter = ("payment_method", "payment_date")
    search_fields = (
        "customer_treatment__name",
        "customer_treatment__phone_number",
        "remarks",
    )
    raw_id_fields = ("customer_treatment", "created_by")
