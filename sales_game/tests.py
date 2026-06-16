from django.contrib.auth import get_user_model
from django.test import TestCase

from account.models import Franchise
from sales.models import Inventory, Order, OrderProduct, Product
from sales_game.models import (
    Game,
    GameCondition,
    GameConditionRule,
    GameWinner,
    check_order_for_games,
)

User = get_user_model()


class GameLogicTestCase(TestCase):
    def setUp(self):
        # Create user & franchise
        self.franchise = Franchise.objects.create(name="Test Franchise")
        self.user = User.objects.create_user(
            username="salesperson",
            password="password123",
            role="SalesPerson",
            franchise=self.franchise,
        )

        # Create Products
        self.sachet_oil = Product.objects.create(
            name="Sachet Oil", status="finished_product"
        )
        self.shampoo_bottle = Product.objects.create(
            name="Shampoo Bottle", status="finished_product"
        )
        self.sunflower_oil = Product.objects.create(
            name="Sunflower Oil", status="finished_product"
        )
        self.mint_shampoo = Product.objects.create(
            name="Mint Shampoo Bottle", status="finished_product"
        )
        self.body_lotion = Product.objects.create(
            name="Body Lotion", status="finished_product"
        )

        # Create Inventories (since OrderProduct links to Inventory)
        self.inv_sachet_oil = Inventory.objects.create(
            product=self.sachet_oil, franchise=self.franchise, quantity=100
        )
        self.inv_shampoo_bottle = Inventory.objects.create(
            product=self.shampoo_bottle, franchise=self.franchise, quantity=100
        )
        self.inv_sunflower_oil = Inventory.objects.create(
            product=self.sunflower_oil, franchise=self.franchise, quantity=100
        )
        self.inv_mint_shampoo = Inventory.objects.create(
            product=self.mint_shampoo, franchise=self.franchise, quantity=100
        )
        self.inv_body_lotion = Inventory.objects.create(
            product=self.body_lotion, franchise=self.franchise, quantity=100
        )

        # Create Game
        self.game = Game.objects.create(name="Test Game", is_active=True)

        # Condition 1: Sachet Oil + Shampoo Bottle
        self.cond_sachet_shampoo = GameCondition.objects.create(
            game=self.game, is_active=True
        )
        GameConditionRule.objects.create(
            condition=self.cond_sachet_shampoo,
            rule_type="product",
            product=self.sachet_oil,
            min_quantity=1,
        )
        GameConditionRule.objects.create(
            condition=self.cond_sachet_shampoo,
            rule_type="product",
            product=self.shampoo_bottle,
            min_quantity=1,
        )

        # Condition 2: 3 piece oil + 3 piece shampoo (any oil or shampoo)
        self.cond_bulk = GameCondition.objects.create(game=self.game, is_active=True)
        GameConditionRule.objects.create(
            condition=self.cond_bulk, rule_type="keyword", keyword="oil", min_quantity=3
        )
        GameConditionRule.objects.create(
            condition=self.cond_bulk,
            rule_type="keyword",
            keyword="shampoo",
            min_quantity=3,
        )

        # Set Condition 1 as active initially
        self.game.active_condition = self.cond_sachet_shampoo
        self.game.save()

    def test_sachet_shampoo_condition_met(self):
        # Create an order containing sachet oil & shampoo bottle
        order = Order.objects.create(
            sales_person=self.user,
            franchise=self.franchise,
            full_name="John Doe",
            phone_number="9876543210",
            payment_method="Cash on Delivery",
        )
        OrderProduct.objects.create(
            order=order, product=self.inv_sachet_oil, quantity=1
        )
        OrderProduct.objects.create(
            order=order, product=self.inv_shampoo_bottle, quantity=2
        )

        assert self.cond_sachet_shampoo.check_order_matches(order)

        # Test helper function
        check_order_for_games(order)
        assert GameWinner.objects.filter(order=order).count() == 1
        winner = GameWinner.objects.get(order=order)
        assert winner.condition == self.cond_sachet_shampoo

    def test_sachet_shampoo_condition_not_met(self):
        # Order containing only sachet oil
        order = Order.objects.create(
            sales_person=self.user,
            franchise=self.franchise,
            full_name="John Doe",
            phone_number="9876543210",
            payment_method="Cash on Delivery",
        )
        OrderProduct.objects.create(
            order=order, product=self.inv_sachet_oil, quantity=5
        )

        assert not self.cond_sachet_shampoo.check_order_matches(order)

        check_order_for_games(order)
        assert GameWinner.objects.filter(order=order).count() == 0

    def test_bulk_condition_met(self):
        # Set Condition 2 as active
        self.game.active_condition = self.cond_bulk
        self.game.save()

        # Order Sunflower Oil (qty 2) + Sachet Oil (qty 1) + Mint Shampoo (qty 3)
        order = Order.objects.create(
            sales_person=self.user,
            franchise=self.franchise,
            full_name="Jane Doe",
            phone_number="9876543211",
            payment_method="Cash on Delivery",
        )
        OrderProduct.objects.create(
            order=order, product=self.inv_sunflower_oil, quantity=2
        )
        OrderProduct.objects.create(
            order=order, product=self.inv_sachet_oil, quantity=1
        )
        OrderProduct.objects.create(
            order=order, product=self.inv_mint_shampoo, quantity=3
        )

        assert self.cond_bulk.check_order_matches(order)

        check_order_for_games(order)
        assert GameWinner.objects.filter(order=order).count() == 1
        winner = GameWinner.objects.get(order=order)
        assert winner.condition == self.cond_bulk

    def test_choose_random_condition(self):
        # Clear active condition
        self.game.active_condition = None
        self.game.save()

        chosen = self.game.choose_random_condition()
        assert chosen is not None
        assert chosen in [self.cond_sachet_shampoo, self.cond_bulk]
        assert self.game.active_condition == chosen
