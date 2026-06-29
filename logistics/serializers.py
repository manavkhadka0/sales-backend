from rest_framework import serializers

from account.serializers import SmallUserSerializer

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
        fields = [
            "id",
            "order",
            "user",
            "assigned_at",
            "is_rider_verified",
            "ydm_delivery_charge",
            "delivery_location_type",
            "ydm_cancelled_charge",
        ]


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
            obj.report_invoices
            .exclude(comment__isnull=True)
            .exclude(comment__exact="")
            .count()
        )


class ReportInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportInvoice
        fields = ["id", "invoice", "reported_by", "comment", "created_at", "updated_at"]


class FranchiseStatementSerializer(serializers.Serializer):
    date = serializers.DateField()
    total_order = serializers.IntegerField()
    total_amount = serializers.FloatField()
    delivery_count = serializers.IntegerField()
    cash_in = serializers.FloatField()
    delivery_charge = serializers.FloatField()
    payment = serializers.FloatField()
    balance = serializers.FloatField()


class RiderPayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiderPayout
        fields = ["id", "rider", "amount", "paid_at", "remarks"]


class RiderCommissionRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiderCommissionRate
        fields = ["id", "order_min_amount", "order_max_amount", "commission_amount"]


class YdmLogisticsSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = YdmLogisticsSetting
        fields = ["id", "inside_ringroad_charge", "outside_ringroad_charge", "cancelled_charge"]
