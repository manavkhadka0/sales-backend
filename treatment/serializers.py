from django.contrib.auth import get_user_model
from rest_framework import serializers

from account.models import Franchise

from .models import (
    PACKAGE_PRICES,
    CustomerTreatment,
    Image,
    PaymentHistory,
    TreatmentType,
)
from .services.treatment_service import TreatmentService

User = get_user_model()


class FranchiseMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Franchise
        fields = ["id", "name", "short_form"]


class ServiceByUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email", "full_name"]

    def get_full_name(self, obj):
        name = f"{obj.first_name} {obj.last_name}".strip()
        return name if name else obj.username


class ImageSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = Image
        fields = [
            "id",
            "customer_treatment",
            "day_number",
            "image",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_day_number(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError(
                "Day number must be a positive integer (e.g. 1, 4, 8, 12...)."
            )
        return value


class PaymentHistorySerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )
    created_by_details = ServiceByUserSerializer(source="created_by", read_only=True)
    created_by = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = PaymentHistory
        fields = [
            "id",
            "customer_treatment",
            "amount",
            "payment_method",
            "payment_method_display",
            "payment_screenshot",
            "remarks",
            "created_by",
            "created_by_details",
            "payment_date",
            "updated_at",
        ]
        read_only_fields = ["payment_date", "updated_at"]


class CustomerTreatmentSerializer(serializers.ModelSerializer):
    images = ImageSerializer(many=True, required=False)
    payment_history = PaymentHistorySerializer(many=True, read_only=True)
    treatment_type_display = serializers.CharField(
        source="get_treatment_type_display", read_only=True
    )
    package_display = serializers.CharField(
        source="get_package_display", read_only=True
    )
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )
    package_price = serializers.SerializerMethodField()
    calculated_total_amount = serializers.FloatField(read_only=True)
    total_paid = serializers.FloatField(read_only=True)
    due_amount = serializers.FloatField(read_only=True)
    payment_status = serializers.CharField(read_only=True)

    franchise_details = FranchiseMinimalSerializer(source="franchise", read_only=True)
    franchise = serializers.PrimaryKeyRelatedField(
        queryset=Franchise.objects.all(), required=False, allow_null=True
    )

    service_by_details = ServiceByUserSerializer(source="service_by", read_only=True)
    service_by = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = CustomerTreatment
        fields = [
            "id",
            "name",
            "phone_number",
            "address",
            "treatment_type",
            "treatment_type_display",
            "package",
            "package_display",
            "package_price",
            "total_amount",
            "paid_amount",
            "calculated_total_amount",
            "total_paid",
            "due_amount",
            "payment_status",
            "payment_method",
            "payment_method_display",
            "reason",
            "franchise",
            "franchise_details",
            "service_by",
            "service_by_details",
            "payment_screenshot",
            "images",
            "payment_history",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_package_price(self, obj):
        if obj.package and obj.package in PACKAGE_PRICES:
            return PACKAGE_PRICES[obj.package]
        return None

    def validate(self, attrs):
        treatment_type = attrs.get(
            "treatment_type", getattr(self.instance, "treatment_type", None)
        )
        package = attrs.get("package", getattr(self.instance, "package", None))
        reason = attrs.get("reason", getattr(self.instance, "reason", None))

        if treatment_type == TreatmentType.PACKAGE_MEMBER:
            if not package:
                raise serializers.ValidationError({
                    "package": "Package selection is required when treatment type is Package Member."
                })
        else:
            attrs["package"] = None

        if treatment_type == TreatmentType.FREE_SERVICE:
            if not reason or not str(reason).strip():
                raise serializers.ValidationError({
                    "reason": "Reason is required when treatment type is Free Service."
                })

        return attrs

    def create(self, validated_data):
        return TreatmentService.create_customer_treatment(validated_data)

    def update(self, instance, validated_data):
        return TreatmentService.update_customer_treatment(instance, validated_data)
