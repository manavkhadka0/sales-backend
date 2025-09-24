from rest_framework import serializers

from .models import (
    Customer,
    FixOffer,
    GiftItem,
    LuckyDrawSystem,
    Offer,
    OfferCondition,
)


class GiftItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = GiftItem
        fields = "__all__"


class GetOrganiazationDetail(serializers.ModelSerializer):
    class Meta:
        model = LuckyDrawSystem
        fields = "__all__"
        depth = 1


class LuckyDrawSystemSerializer(serializers.ModelSerializer):
    class Meta:
        model = LuckyDrawSystem
        fields = [
            "id",
            "name",
            "franchise",
            "description",
            "background_image",
            "hero_image",
            "main_offer_stamp_image",
            "qr",
            "start_date",
            "end_date",
        ]
        read_only_fields = ["created_at", "updated_at"]


class FixOfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = FixOffer
        fields = ["lucky_draw_system", "phone_number", "quantity", "gift"]


class OfferConditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferCondition
        fields = "__all__"


class OfferSerializer(serializers.ModelSerializer):
    gift = serializers.PrimaryKeyRelatedField(
        many=True, queryset=GiftItem.objects.all()
    )

    class Meta:
        model = Offer
        fields = "__all__"


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["__all__"]


class CustomerGiftSerializer(serializers.ModelSerializer):
    gift = GiftItemSerializer(many=True)

    class Meta:
        model = Customer
        fields = [
            "full_name",
            "gift",
            "prize_details",
            "date_of_purchase",
        ]
