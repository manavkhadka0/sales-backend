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

    def test_game_can_only_be_won_once_globally(self):
        # Create a second user (salesperson)
        user2 = User.objects.create_user(
            username="salesperson2",
            password="password123",
            role="SalesPerson",
            franchise=self.franchise,
        )

        # Order 1 placed by salesperson self.user (met condition)
        order1 = Order.objects.create(
            sales_person=self.user,
            franchise=self.franchise,
            full_name="Customer One",
            phone_number="9876543210",
            payment_method="Cash on Delivery",
        )
        OrderProduct.objects.create(
            order=order1, product=self.inv_sachet_oil, quantity=1
        )
        OrderProduct.objects.create(
            order=order1, product=self.inv_shampoo_bottle, quantity=2
        )
        check_order_for_games(order1)
        assert GameWinner.objects.filter(game=self.game).count() == 1

        # Order 2 placed by different salesperson user2 (also met condition)
        order2 = Order.objects.create(
            sales_person=user2,
            franchise=self.franchise,
            full_name="Customer Two",
            phone_number="9876543211",
            payment_method="Cash on Delivery",
        )
        OrderProduct.objects.create(
            order=order2, product=self.inv_sachet_oil, quantity=1
        )
        OrderProduct.objects.create(
            order=order2, product=self.inv_shampoo_bottle, quantity=2
        )
        check_order_for_games(order2)

        # Game should still only have 1 winning order in total globally
        assert GameWinner.objects.filter(game=self.game).count() == 1
        # Order 2 should not be registered as a winner
        assert not GameWinner.objects.filter(order=order2).exists()

    def test_game_inactive_by_default(self):
        new_game = Game.objects.create(name="Default Game")
        assert not new_game.is_active

    def test_active_game_singleton_behavior(self):
        # self.game is active
        self.game.is_active = True
        self.game.save()
        assert self.game.is_active

        game2 = Game.objects.create(name="Game 2", is_active=True)
        # self.game should be deactivated
        self.game.refresh_from_db()
        assert not self.game.is_active
        assert game2.is_active

    def test_active_game_becomes_null_on_win(self):
        # self.game is active
        self.game.is_active = True
        self.game.save()

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

        check_order_for_games(order)
        # The game should be deactivated (is_active = False)
        self.game.refresh_from_db()
        assert not self.game.is_active

        # There should be no active game
        active = Game.objects.filter(is_active=True).first()
        assert active is None

    def test_active_game_api_null_when_no_active_game(self):
        from django.urls import reverse
        from rest_framework.test import APIClient
        
        client = APIClient()
        client.force_authenticate(user=self.user)

        # Deactivate all games
        Game.objects.all().update(is_active=False)

        url = reverse("sales_game:active-game")
        response = client.get(url)
        assert response.status_code == 200
        assert response.data is None

    def test_update_game_is_active_api(self):
        from django.urls import reverse
        from rest_framework.test import APIClient
        
        client = APIClient()
        client.force_authenticate(user=self.user)

        # Create two games, both initially inactive
        game1 = Game.objects.create(name="Game 1", is_active=False)
        game2 = Game.objects.create(name="Game 2", is_active=False)

        # Activate game1 via API
        url = reverse("sales_game:game-detail", kwargs={"pk": game1.pk})
        response = client.patch(url, {"is_active": True}, format="json")
        assert response.status_code == 200
        assert response.data["is_active"] is True

        game1.refresh_from_db()
        assert game1.is_active

        # Now activate game2 via API, game1 should be deactivated automatically
        url2 = reverse("sales_game:game-detail", kwargs={"pk": game2.pk})
        response2 = client.patch(url2, {"is_active": True}, format="json")
        assert response2.status_code == 200
        assert response2.data["is_active"] is True

        game1.refresh_from_db()
        game2.refresh_from_db()
        assert not game1.is_active
        assert game2.is_active
