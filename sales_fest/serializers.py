from rest_framework import serializers

from account.models import CustomUser, Franchise
from account.serializers import UserSerializer
from lucky_draw.models import LuckyDrawSystem

from .models import FestConfig, SalesGroup


class SalesGroupSerializer(serializers.ModelSerializer):
    leader = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(), allow_null=True, required=False
    )
    members = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(), many=True, required=False
    )

    class Meta:
        model = SalesGroup
        fields = [
            "id",
            "group_name",
            "leader",
            "members",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SalesGroupSerializer2(serializers.ModelSerializer):
    leader = UserSerializer(read_only=True)
    members = UserSerializer(many=True, read_only=True)

    class Meta:
        model = SalesGroup
        fields = [
            "id",
            "group_name",
            "leader",
            "members",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class FestConfigSerializer(serializers.ModelSerializer):
    franchise = serializers.PrimaryKeyRelatedField(queryset=Franchise.objects.all())
    lucky_draw_system = serializers.PrimaryKeyRelatedField(
        queryset=LuckyDrawSystem.objects.all(), allow_null=True, required=False
    )
    sales_group = serializers.PrimaryKeyRelatedField(
        queryset=SalesGroup.objects.all(), many=True, required=False
    )

    class Meta:
        model = FestConfig
        fields = [
            "id",
            "franchise",
            "has_lucky_draw",
            "lucky_draw_system",
            "has_sales_fest",
            "sales_group",
        ]
        read_only_fields = ["id"]

    def update(self, instance, validated_data):
        # Clear lucky_draw_system if has_lucky_draw=False
        if validated_data.get("has_lucky_draw") is False:
            instance.lucky_draw_system = None
        return super().update(instance, validated_data)
