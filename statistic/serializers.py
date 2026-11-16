from rest_framework import serializers

from account.serializers import UserSerializer
from .models import Report


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = "__all__"


class ReportListSerializer(serializers.ModelSerializer):
    franchise_name = serializers.CharField(source="franchise.name", read_only=True)
    reported_by = UserSerializer()

    class Meta:
        model = Report
        fields = [
            "id",
            "franchise_name",
            "reported_by",
            "message_received_fb",
            "message_received_whatsapp",
            "message_received_tiktok",
            "call_received",
            "customer_follow_up",
            "new_customer",
            "daily_dollar_spending",
            "customer_to_package",
            "free_treatment",
            "remarks",
            "date",
            "created_at",
            "updated_at",
        ]


# Streamlined Franchise Sales & Product Report Serializer


class FranchiseReportItemSerializer(serializers.Serializer):
    franchise_id = serializers.IntegerField(required=False, allow_null=True)
    franchise_name = serializers.CharField()
    total_sales = serializers.IntegerField()
    online_sales = serializers.IntegerField()
    office_sale = serializers.IntegerField()
    product_breakdown = serializers.DictField(child=serializers.IntegerField())
