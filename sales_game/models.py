import random

from django.db import models

from sales.models import Order, Product


class Game(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    active_condition = models.ForeignKey(
        "GameCondition",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="The currently selected/active condition for this game",
    )
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_active:
            # Enforce that only one game is active at a time
            Game.objects.filter(is_active=True).exclude(pk=self.pk).update(
                is_active=False
            )
        super().save(*args, **kwargs)

    def choose_random_condition(self):
        """
        Randomly select one of the active conditions for this game and set it as active_condition.
        """
        conditions = self.conditions.filter(is_active=True)
        if conditions.exists():
            selected = random.choice(list(conditions))
            self.active_condition = selected
            self.save(update_fields=["active_condition"])
            return selected
        return None


class GameCondition(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="conditions")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        # Dynamically build a condition string from its rules
        rules = self.rules.all()
        if rules.exists():
            rules_str = " + ".join([
                f"{r.min_quantity}x {r.product.name if r.rule_type == 'product' and r.product else r.keyword}"
                for r in rules
            ])
            return f"Condition: {rules_str}"
        return f"Condition (ID: {self.id} - No Rules)"

    def check_order_matches(self, order):
        """
        Evaluate if a given order matches all rules of this condition.
        """
        rules = self.rules.all()
        if not rules.exists():
            return False

        # Order products are related via Inventory. Select_related optimizes performance.
        order_products = order.order_products.select_related("product__product").all()
        if not order_products:
            return False

        for rule in rules:
            if rule.rule_type == "product":
                if not rule.product:
                    return False
                # Calculate total quantity of this specific product ordered
                matching_qty = sum(
                    op.quantity
                    for op in order_products
                    if op.product.product == rule.product
                )
                if matching_qty < rule.min_quantity:
                    return False
            elif rule.rule_type == "keyword":
                if not rule.keyword:
                    return False
                keyword = rule.keyword.strip().lower()
                # Calculate total quantity of any product whose name contains the keyword
                matching_qty = sum(
                    op.quantity
                    for op in order_products
                    if keyword in op.product.product.name.lower()
                )
                if matching_qty < rule.min_quantity:
                    return False
        return True


class GameConditionRule(models.Model):
    RULE_TYPE_CHOICES = [
        ("product", "Specific Product"),
        ("keyword", "Keyword in Product Name"),
    ]

    condition = models.ForeignKey(
        GameCondition, on_delete=models.CASCADE, related_name="rules"
    )
    rule_type = models.CharField(
        max_length=20, choices=RULE_TYPE_CHOICES, default="product"
    )

    # Required for 'product' rule type
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True
    )

    # Required for 'keyword' rule type (e.g. "oil", "shampoo")
    keyword = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Case-insensitive partial match on product name",
    )

    min_quantity = models.PositiveIntegerField(
        default=1, help_text="Minimum quantity required"
    )

    def __str__(self):
        if self.rule_type == "product":
            target = self.product.name if self.product else "None"
        else:
            target = f"keyword '{self.keyword}'"
        return f"Rule: {target} (min {self.min_quantity})"


class GameWinner(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    condition = models.ForeignKey(GameCondition, on_delete=models.CASCADE)
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="game_winners"
    )
    won_at = models.DateTimeField(auto_now_add=True)
    notified = models.BooleanField(default=False)
    message = models.TextField(blank=True)

    def __str__(self):
        return f"Order {self.order.order_code} won {str(self.condition)}"


def check_order_for_games(order):
    """
    Check if the newly created order satisfies any active game's active condition.
    If so, record a GameWinner.
    A salesperson can only win once per game.
    """
    active_game = Game.objects.filter(is_active=True).first()
    if not active_game or not active_game.active_condition:
        return

    # Check if this game has already been won by anyone (once won, no one else can win)
    if GameWinner.objects.filter(game=active_game).exists():
        return

    condition = active_game.active_condition
    if condition.check_order_matches(order):
        # Record the win
        winner, created = GameWinner.objects.get_or_create(
            game=active_game,
            condition=condition,
            order=order,
            defaults={
                "message": f"Congratulations! You won the '{active_game.name}' game by satisfying condition: '{str(condition)}'"
            },
        )
        if created:
            # Once won, deactivate this game so active game becomes null/inactive
            active_game.is_active = False
            active_game.save(update_fields=["is_active"])
