from rest_framework import serializers

from tracking.models import SalesPersonLocation, SalesPersonLocationHistory


class SalesPersonLocationPingSerializer(serializers.Serializer):
    """
    Serializer for mobile GPS location pings submitted by offline salespersons.
    """

    latitude = serializers.FloatField(
        min_value=-90.0,
        max_value=90.0,
        help_text="Current latitude (-90.0 to 90.0)",
    )
    longitude = serializers.FloatField(
        min_value=-180.0,
        max_value=180.0,
        help_text="Current longitude (-180.0 to 180.0)",
    )
    accuracy = serializers.FloatField(
        required=False,
        allow_null=True,
        help_text="GPS accuracy in meters",
    )
    recorded_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text="Timestamp recorded on device (ISO 8601)",
    )


class SalesPersonToggleOnlineSerializer(serializers.Serializer):
    """
    Serializer for switching a salesperson's online/offline availability status.
    """

    is_online = serializers.BooleanField(
        help_text="True for online/in field, False for offline"
    )


class SalesPersonSinglePingInputSerializer(serializers.Serializer):
    """
    Single coordinate point inside an offline batch upload.
    """

    latitude = serializers.FloatField(min_value=-90.0, max_value=90.0)
    longitude = serializers.FloatField(min_value=-180.0, max_value=180.0)
    accuracy = serializers.FloatField(required=False, allow_null=True)
    recorded_at = serializers.DateTimeField(required=False, allow_null=True)


class SalesPersonBatchPingSerializer(serializers.Serializer):
    """
    Serializer for batch-uploading location points saved locally during offline field visits.
    """

    pings = serializers.ListField(
        child=SalesPersonSinglePingInputSerializer(),
        allow_empty=False,
        help_text="Chronological list of offline-buffered GPS coordinates",
    )


class SalesPersonLiveLocationSerializer(serializers.ModelSerializer):
    """
    Comprehensive live location details tailored for the manager/admin dashboard map.
    Includes dynamic heartbeat status verification.
    """

    salesperson_id = serializers.IntegerField(source="salesperson.id", read_only=True)
    username = serializers.CharField(source="salesperson.username", read_only=True)
    full_name = serializers.SerializerMethodField()
    phone_number = serializers.CharField(
        source="salesperson.phone_number", read_only=True
    )
    role = serializers.CharField(source="salesperson.role", read_only=True)
    franchise_id = serializers.IntegerField(
        source="salesperson.franchise.id",
        read_only=True,
        allow_null=True,
    )
    franchise_name = serializers.CharField(
        source="salesperson.franchise.name",
        read_only=True,
        allow_null=True,
    )
    tracking_status = serializers.CharField(read_only=True)
    is_active_now = serializers.BooleanField(read_only=True)
    seconds_since_last_ping = serializers.IntegerField(read_only=True)

    class Meta:
        model = SalesPersonLocation
        fields = [
            "id",
            "salesperson_id",
            "username",
            "full_name",
            "phone_number",
            "role",
            "franchise_id",
            "franchise_name",
            "latitude",
            "longitude",
            "accuracy",
            "is_online",
            "is_active_now",
            "tracking_status",
            "seconds_since_last_ping",
            "last_updated_at",
        ]

    def get_full_name(self, obj) -> str:
        salesperson = obj.salesperson
        name = f"{salesperson.first_name} {salesperson.last_name}".strip()
        return name or salesperson.username


class SalesPersonLocationHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for route history breadcrumb trails.
    """

    salesperson_id = serializers.IntegerField(source="salesperson.id", read_only=True)
    salesperson_name = serializers.SerializerMethodField()

    class Meta:
        model = SalesPersonLocationHistory
        fields = [
            "id",
            "salesperson_id",
            "salesperson_name",
            "latitude",
            "longitude",
            "accuracy",
            "recorded_at",
            "created_at",
        ]

    def get_salesperson_name(self, obj) -> str:
        salesperson = obj.salesperson
        name = f"{salesperson.first_name} {salesperson.last_name}".strip()
        return name or salesperson.username
