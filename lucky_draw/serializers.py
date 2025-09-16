from rest_framework import serializers
from .models import (
    GiftItem,
    LuckyDrawSystem,
    RechargeCard,
    IMEINO,
    FixOffer,
    MobileOfferCondition,
    MobilePhoneOffer,
    RechargeCardOffer,
    ElectronicsShopOffer,
    Customer,
    RechargeCardCondition,
    ElectronicOfferCondition,
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
            "description",
            "background_image",
            "hero_image",
            "main_offer_stamp_image",
            "qr",
            "type",
            "start_date",
            "end_date",
            'how_to_participate',
            'redeem_condition',
            "terms_and_conditions",
        ]
        read_only_fields = ["created_at", "updated_at"]


class RechargeCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = RechargeCard
        fields = ["lucky_draw_system", "cardno",
                  "provider", "amount", "is_assigned"]


class IMEINOSerializer(serializers.ModelSerializer):
    class Meta:
        model = IMEINO
        fields = ["lucky_draw_system", "imei_no", "phone_model"]


class FixOfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = FixOffer
        fields = ["lucky_draw_system", "imei_no", "quantity", "gift"]


class MobileOfferConditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MobileOfferCondition
        fields = ["id", "offer_condition_name", "condition"]


class MobilePhoneOfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = MobilePhoneOffer
        exclude = ["lucky_draw_system"]
        depth = 1


class RechargeCardOfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = RechargeCardOffer
        fields = "__all__"


class RechargeCardConditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RechargeCardCondition
        fields = "__all__"


class ElectronicShopOfferConditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ElectronicOfferCondition
        fields = "__all__"


class ElectronicsShopOfferSerializer(serializers.ModelSerializer):
    gift = serializers.PrimaryKeyRelatedField(
        many=True, queryset=GiftItem.objects.all()
    )

    class Meta:
        model = ElectronicsShopOffer
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
