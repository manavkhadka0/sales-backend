from rest_framework import serializers

from account.serializers import SmallUserSerializer

from .models import (
    AssignOrder,
    Invoice,
    OrderChangeLog,
    OrderComment,
    ReportInvoice,
)


class OrderChangeLogSerializer(serializers.ModelSerializer):
    user = SmallUserSerializer()

    class Meta:
        model = OrderChangeLog
        fields = "__all__"


class OrderCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderComment
        fields = ["id", "order", "user", "comment", "created_at", "updated_at"]


class OrderCommentDetailSerializer(serializers.ModelSerializer):
    user = SmallUserSerializer(read_only=True)

    class Meta:
        model = OrderComment
        fields = ["id", "order", "user", "comment", "created_at", "updated_at"]


class AssignOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssignOrder
        fields = ["id", "order", "user", "assigned_at"]


class InvoiceSerializer(serializers.ModelSerializer):
    comment_count = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "id",
            "franchise",
            "created_by",
            "invoice_code",
            "total_amount",
            "paid_amount",
            "due_amount",
            "payment_type",
            "status",
            "approved_at",
            "is_approved",
            "signature",
            "created_at",
            "updated_at",
            "approved_by",
            "comment_count",
        ]

    def get_comment_count(self, obj):
        # Count only non-null and non-empty comments related to this invoice
        return (
            obj.report_invoices.exclude(comment__isnull=True)
            .exclude(comment__exact="")
            .count()
        )


class ReportInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportInvoice
        fields = ["id", "invoice", "reported_by", "comment", "created_at", "updated_at"]
