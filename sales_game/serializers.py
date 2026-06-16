from rest_framework import serializers

from .models import Game, GameCondition, GameConditionRule, GameWinner


class GameConditionRuleSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source="product.name")

    class Meta:
        model = GameConditionRule
        fields = ["id", "rule_type", "product", "product_name", "keyword", "min_quantity"]


class GameConditionSerializer(serializers.ModelSerializer):
    rules = GameConditionRuleSerializer(many=True, read_only=True)
    name = serializers.SerializerMethodField()

    class Meta:
        model = GameCondition
        fields = ["id", "name", "description", "is_active", "rules"]

    def get_name(self, obj):
        return str(obj)


class GameSerializer(serializers.ModelSerializer):
    conditions = GameConditionSerializer(many=True, read_only=True)
    active_condition_name = serializers.SerializerMethodField()

    class Meta:
        model = Game
        fields = [
            "id",
            "name",
            "description",
            "is_active",
            "active_condition",
            "active_condition_name",
            "conditions",
            "created_at",
            "updated_at",
        ]

    def get_active_condition_name(self, obj):
        return str(obj.active_condition) if obj.active_condition else None


# ------------------ WRITABLE NESTED SERIALIZERS ------------------ #

class GameConditionRuleWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameConditionRule
        fields = ["rule_type", "product", "keyword", "min_quantity"]


class GameConditionWriteSerializer(serializers.ModelSerializer):
    rules = GameConditionRuleWriteSerializer(many=True, required=False)

    class Meta:
        model = GameCondition
        fields = ["description", "is_active", "rules"]


class GameCreateSerializer(serializers.ModelSerializer):
    conditions = GameConditionWriteSerializer(many=True, required=False)

    class Meta:
        model = Game
        fields = ["name", "description", "is_active", "conditions"]

    def create(self, validated_data):
        conditions_data = validated_data.pop("conditions", [])
        
        # If this game is set to active, deactivate other games first
        is_active = validated_data.get("is_active", True)
        if is_active:
            Game.objects.filter(is_active=True).update(is_active=False)

        game = Game.objects.create(**validated_data)

        for cond_data in conditions_data:
            rules_data = cond_data.pop("rules", [])
            condition = GameCondition.objects.create(game=game, **cond_data)
            
            for rule_data in rules_data:
                GameConditionRule.objects.create(condition=condition, **rule_data)

        # Set the first condition as active condition by default if it exists
        first_condition = game.conditions.first()
        if first_condition:
            game.active_condition = first_condition
            game.save(update_fields=["active_condition"])

        return game


# ------------------ WINNER SERIALIZER ------------------ #

class GameWinnerSerializer(serializers.ModelSerializer):
    game_name = serializers.ReadOnlyField(source="game.name")
    condition_name = serializers.SerializerMethodField()
    order_code = serializers.ReadOnlyField(source="order.order_code")
    customer_name = serializers.ReadOnlyField(source="order.full_name")

    class Meta:
        model = GameWinner
        fields = [
            "id",
            "game",
            "game_name",
            "condition",
            "condition_name",
            "order",
            "order_code",
            "customer_name",
            "won_at",
            "notified",
            "message",
        ]

    def get_condition_name(self, obj):
        return str(obj.condition) if obj.condition else None
