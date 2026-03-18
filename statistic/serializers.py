from rest_framework import serializers

from .models import Report
from account.serializers import UserSerializer


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = "__all__"


class ReportListSerializer(serializers.ModelSerializer):
    franchise_name = serializers.CharField(source="franchise.name", read_only=True)
    reported_by=UserSerializer()

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
