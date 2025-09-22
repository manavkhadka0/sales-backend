from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import (
    AssignOrder,
    Invoice,
    OrderChangeLog,
    OrderComment,
    ReportInvoice,
)

# Register your models here.


class OrderChangeLogAdmin(ModelAdmin):
    list_display = (
        "order",
        "user",
        "old_status",
        "new_status",
        "comment",
        "changed_at",
    )
    list_filter = ("order", "user", "old_status", "new_status", "changed_at")
    search_fields = (
        "order__order_code",
        "user__first_name",
        "old_status",
        "new_status",
        "comment",
    )
    ordering = ("-changed_at",)


admin.site.register(OrderChangeLog, OrderChangeLogAdmin)


class OrderCommentAdmin(ModelAdmin):
    list_display = ("order", "user", "comment", "created_at", "updated_at")
    list_filter = ("order", "user", "created_at", "updated_at")
    search_fields = ("order", "user", "comment")
    ordering = ("-created_at",)


admin.site.register(OrderComment, OrderCommentAdmin)


class AssignOrderAdmin(ModelAdmin):
    list_display = ("order", "user", "assigned_at")
    list_filter = ("order", "user", "assigned_at")
    search_fields = ("order", "user", "assigned_at")
    ordering = ("-assigned_at",)


admin.site.register(AssignOrder, AssignOrderAdmin)


class InvoiceAdmin(ModelAdmin):
    list_display = (
        "franchise",
        "created_by",
        "invoice_code",
        "total_amount",
        "paid_amount",
        "due_amount",
        "payment_type",
        "status",
        "is_approved",
        "created_at",
    )
    list_filter = (
        "franchise",
        "created_by",
        "payment_type",
        "status",
        "is_approved",
        "created_at",
    )
    ordering = ("-created_at",)


admin.site.register(Invoice, InvoiceAdmin)


class ReportInvoiceAdmin(ModelAdmin):
    list_display = ("invoice", "reported_by", "comment", "created_at", "updated_at")
    list_filter = ("invoice", "reported_by", "created_at", "updated_at")
    search_fields = ("invoice", "reported_by", "comment")
    ordering = ("-created_at",)


admin.site.register(ReportInvoice, ReportInvoiceAdmin)
