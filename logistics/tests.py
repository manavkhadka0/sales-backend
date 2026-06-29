from datetime import date
from decimal import Decimal
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from account.models import CustomUser, Franchise
from sales.models import Order
from logistics.models import OrderChangeLog, AssignOrder, YdmLogisticsSetting


class RiderDailyStatsViewTests(APITestCase):
    def setUp(self):
        # Create users
        self.rider_user = CustomUser.objects.create_user(
            username="rider1",
            email="rider1@example.com",
            phone_number="9876543210",
            password="password123",
            role="YDM_Rider",
        )
        self.operator_user = CustomUser.objects.create_user(
            username="operator1",
            email="operator1@example.com",
            phone_number="9876543211",
            password="password123",
            role="YDM_Operator",
        )
        self.unauthorized_user = CustomUser.objects.create_user(
            username="sales1",
            email="sales1@example.com",
            phone_number="9876543212",
            password="password123",
            role="SalesPerson",
        )

        # Create a salesperson for Order foreign key
        self.sales_person = CustomUser.objects.create_user(
            username="salesperson",
            email="salesperson@example.com",
            phone_number="9876543213",
            password="password123",
            role="SalesPerson",
        )

        # Create orders
        self.order1 = Order.objects.create(
            full_name="Customer One",
            phone_number="9800000001",
            payment_method="Cash on Delivery",
            sales_person=self.sales_person,
        )
        self.order2 = Order.objects.create(
            full_name="Customer Two",
            phone_number="9800000002",
            payment_method="Cash on Delivery",
            sales_person=self.sales_person,
        )
        self.order3 = Order.objects.create(
            full_name="Customer Three",
            phone_number="9800000003",
            payment_method="Prepaid",
            sales_person=self.sales_person,
        )

        # Assign orders to rider
        AssignOrder.objects.create(order=self.order1, user=self.rider_user)
        AssignOrder.objects.create(order=self.order2, user=self.rider_user)
        AssignOrder.objects.create(order=self.order3, user=self.rider_user)

        self.url = reverse("rider-daily-stats")

    def test_unauthenticated_access(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthorized_role_access(self):
        self.client.force_authenticate(user=self.unauthorized_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_rider_daily_stats_default_month(self):
        # Authenticate as rider
        self.client.force_authenticate(user=self.rider_user)

        # Create OrderChangeLogs for today
        log1 = OrderChangeLog.objects.create(
            order=self.order1,
            user=self.rider_user,
            old_status="Verified",
            new_status="Delivered",
        )
        log2 = OrderChangeLog.objects.create(
            order=self.order2,
            user=self.rider_user,
            old_status="Verified",
            new_status="Cancelled",
        )

        # Overwrite changed_at to today (using auto_now_add override)
        today = timezone.localdate()
        today_datetime = timezone.make_aware(timezone.datetime(today.year, today.month, today.day, 12, 0, 0))
        OrderChangeLog.objects.filter(id__in=[log1.id, log2.id]).update(changed_at=today_datetime)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify today's date has counts
        today_str = today.strftime("%Y-%m-%d")
        data = response.json()
        self.assertTrue(len(data) >= 1)
        today_stat = next((item for item in data if item["date"] == today_str), None)
        self.assertIsNotNone(today_stat)
        self.assertEqual(today_stat["delivered_count"], 1)
        self.assertEqual(today_stat["returned_count"], 1)

    def test_rider_daily_stats_custom_filter(self):
        self.client.force_authenticate(user=self.rider_user)

        # Create old change log (outside default current month if we run on e.g. first of month,
        # but let's set it to a specific past date and filter by that date)
        past_date = date(2026, 5, 10)
        past_datetime = timezone.make_aware(timezone.datetime(2026, 5, 10, 10, 0, 0))

        log = OrderChangeLog.objects.create(
            order=self.order3,
            user=self.rider_user,
            old_status="Verified",
            new_status="Returned By Customer",
        )
        OrderChangeLog.objects.filter(id=log.id).update(changed_at=past_datetime)

        # Filter with date range containing the past date
        response = self.client.get(self.url, {"start_date": "2026-05-01", "end_date": "2026-05-15"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["date"], "2026-05-10")
        self.assertEqual(data[0]["delivered_count"], 0)
        self.assertEqual(data[0]["returned_count"], 1)

    def test_operator_access_for_rider(self):
        self.client.force_authenticate(user=self.operator_user)

        # Create OrderChangeLogs for today
        log = OrderChangeLog.objects.create(
            order=self.order1,
            user=self.rider_user,
            old_status="Verified",
            new_status="Delivered",
        )
        today = timezone.localdate()
        today_datetime = timezone.make_aware(timezone.datetime(today.year, today.month, today.day, 12, 0, 0))
        OrderChangeLog.objects.filter(id=log.id).update(changed_at=today_datetime)

        # Non-rider must specify rider parameter
        response_no_rider = self.client.get(self.url)
        self.assertEqual(response_no_rider.status_code, status.HTTP_400_BAD_REQUEST)

        # Correct query with rider's phone number
        response = self.client.get(self.url, {"rider": self.rider_user.phone_number})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(len(data) >= 1)
        today_str = today.strftime("%Y-%m-%d")
        today_stat = next((item for item in data if item["date"] == today_str), None)
        self.assertIsNotNone(today_stat)
        self.assertEqual(today_stat["delivered_count"], 1)
        self.assertEqual(today_stat["returned_count"], 0)


class YdmLogisticsSettingViewTests(APITestCase):
    def setUp(self):
        self.operator_user = CustomUser.objects.create_user(
            username="operator_settings",
            email="op_settings@example.com",
            phone_number="9876543301",
            password="password123",
            role="YDM_Operator",
        )
        self.rider_user = CustomUser.objects.create_user(
            username="rider_settings",
            email="rider_settings@example.com",
            phone_number="9876543302",
            password="password123",
            role="YDM_Rider",
        )
        self.url = reverse("ydm-logistics-settings")

    def test_get_settings_auto_creates(self):
        self.client.force_authenticate(user=self.operator_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["inside_ringroad_charge"], "100.00")
        self.assertEqual(data["outside_ringroad_charge"], "150.00")

    def test_rider_cannot_get_or_update_settings(self):
        self.client.force_authenticate(user=self.rider_user)
        response_get = self.client.get(self.url)
        self.assertEqual(response_get.status_code, status.HTTP_403_FORBIDDEN)

        response_put = self.client.put(self.url, {"inside_ringroad_charge": "120.00"})
        self.assertEqual(response_put.status_code, status.HTTP_403_FORBIDDEN)

    def test_operator_updates_settings(self):
        self.client.force_authenticate(user=self.operator_user)
        response = self.client.patch(self.url, {
            "inside_ringroad_charge": "120.00",
            "outside_ringroad_charge": "180.00"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["inside_ringroad_charge"], "120.00")
        self.assertEqual(data["outside_ringroad_charge"], "180.00")



class RiderVerifyOrderViewTests(APITestCase):
    def setUp(self):
        self.rider_user = CustomUser.objects.create_user(
            username="rider_verify",
            email="rider_verify@example.com",
            phone_number="9876543401",
            password="password123",
            role="YDM_Rider",
        )
        self.sales_person = CustomUser.objects.create_user(
            username="sales_verify",
            email="sales_verify@example.com",
            phone_number="9876543402",
            password="password123",
            role="SalesPerson",
        )
        self.order = Order.objects.create(
            full_name="Customer",
            phone_number="9800000101",
            payment_method="Cash on Delivery",
            sales_person=self.sales_person,
        )
        self.assignment = AssignOrder.objects.create(order=self.order, user=self.rider_user)
        self.url = reverse("rider-verify-order")

    def test_verify_inside_ringroad(self):
        # Create settings first
        YdmLogisticsSetting.objects.create(
            inside_ringroad_charge=Decimal("110.00"),
            outside_ringroad_charge=Decimal("160.00"),
        )

        self.client.force_authenticate(user=self.rider_user)
        response = self.client.post(self.url, {
            "order": self.order.order_code,
            "delivery_location_type": "Inside Ringroad"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["is_rider_verified"], True)
        self.assertEqual(data["delivery_location_type"], "Inside Ringroad")
        self.assertEqual(data["ydm_delivery_charge"], "110.00")

        # Check DB state
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.is_rider_verified, True)
        self.assertEqual(self.assignment.delivery_location_type, "Inside Ringroad")
        self.assertEqual(self.assignment.ydm_delivery_charge, Decimal("110.00"))

    def test_verify_outside_ringroad(self):
        YdmLogisticsSetting.objects.create(
            inside_ringroad_charge=Decimal("110.00"),
            outside_ringroad_charge=Decimal("160.00"),
        )

        self.client.force_authenticate(user=self.rider_user)
        response = self.client.post(self.url, {
            "order": self.order.order_code,
            "delivery_location_type": "Outside Ringroad"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["ydm_delivery_charge"], "160.00")

        # Check DB state
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.ydm_delivery_charge, Decimal("160.00"))

    def test_historical_preservation_on_settings_change(self):
        setting = YdmLogisticsSetting.objects.create(
            inside_ringroad_charge=Decimal("100.00"),
            outside_ringroad_charge=Decimal("150.00"),
        )

        # 1. Verify first order inside ringroad
        self.client.force_authenticate(user=self.rider_user)
        self.client.post(self.url, {
            "order": self.order.order_code,
            "delivery_location_type": "Inside Ringroad"
        })
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.ydm_delivery_charge, Decimal("100.00"))

        # 2. Operator changes settings
        setting.inside_ringroad_charge = Decimal("125.00")
        setting.save()

        # 3. Check historical order remains untouched (stays 100.00)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.ydm_delivery_charge, Decimal("100.00"))

    def test_invalid_choices(self):
        self.client.force_authenticate(user=self.rider_user)
        response = self.client.post(self.url, {
            "order": self.order.order_code,
            "delivery_location_type": "Invalid Location"
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class FranchiseStatementAPIViewTests(APITestCase):
    def setUp(self):
        # Create a Franchise with id=1 to satisfy foreign key integrity checks
        self.franchise = Franchise.objects.create(id=1, name="Test Franchise")
        
        # Create a user/franchise partner if necessary, or just use a dummy id
        self.user = CustomUser.objects.create_user(
            username="partner",
            email="partner@example.com",
            phone_number="9876543501",
            password="password123",
            role="Franchise_Partner",
        )
        self.url = reverse("franchise_statement_full", kwargs={"franchise_id": 1})

    def test_get_statement_empty_db_fallback(self):
        # Authenticate
        self.client.force_authenticate(user=self.user)
        
        # Call API without start_date / end_date params to trigger fallback
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        results = data.get("results", {})
        self.assertEqual(results.get("franchise_id"), 1)
        self.assertIn("start_date", results)
        self.assertIn("end_date", results)
        self.assertIn("statement", results)

    def test_get_statement_with_date_params(self):
        self.client.force_authenticate(user=self.user)
        
        # We need a franchise with ID 1 in db to avoid queries failing, or just pass a date range
        response = self.client.get(self.url, {"start_date": "2026-06-01", "end_date": "2026-06-29"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        results = data.get("results", {})
        self.assertEqual(results.get("start_date"), "2026-06-01")
        self.assertEqual(results.get("end_date"), "2026-06-29")

    def test_get_statement_with_charges(self):
        self.client.force_authenticate(user=self.user)
        
        # 1. Create a Franchise (since franchise_id is referenced)
        # Note: If there's an existing franchise model or franchise_id is just an integer, we might need a model.
        # Let's import Franchise if it exists. Let's see what model Franchise is.
        # Oh, in views.py it does: Order.objects.filter(franchise_id=franchise_id)
        # If there's no FK constraint, we can just use franchise_id=1.
        # Let's check: Order model has franchise_id. Is it a FK?
        # Let's look at views.py line 39: from sales.models import Order
        
        # Let's create a sales person for Order
        sales_person = CustomUser.objects.create_user(
            username="sales_statement",
            email="sales_statement@example.com",
            phone_number="9876543502",
            password="password123",
            role="SalesPerson",
        )
        
        # Create delivered order
        order_delivered = Order.objects.create(
            full_name="Delivered Customer",
            phone_number="9800000201",
            payment_method="Cash on Delivery",
            sales_person=sales_person,
            franchise_id=1,
            logistics="YDM",
            order_status="Delivered",
            total_amount=Decimal("1000.00"),
            prepaid_amount=Decimal("100.00"),
        )
        
        # Create cancelled order
        order_cancelled = Order.objects.create(
            full_name="Cancelled Customer",
            phone_number="9800000202",
            payment_method="Cash on Delivery",
            sales_person=sales_person,
            franchise_id=1,
            logistics="YDM",
            order_status="Cancelled",
            total_amount=Decimal("500.00"),
            prepaid_amount=Decimal("0.00"),
        )
        
        # Create assignments
        AssignOrder.objects.create(
            order=order_delivered,
            user=self.user,
            ydm_delivery_charge=Decimal("150.00"),
        )
        AssignOrder.objects.create(
            order=order_cancelled,
            user=self.user,
            ydm_cancelled_charge=Decimal("50.00"),
        )
        
        # Change their updated_at date so they fall in range
        today = timezone.localdate()
        today_datetime = timezone.make_aware(timezone.datetime(today.year, today.month, today.day, 12, 0, 0))
        Order.objects.filter(id__in=[order_delivered.id, order_cancelled.id]).update(updated_at=today_datetime)
        
        # Call API
        start_str = (today - timezone.timedelta(days=2)).strftime("%Y-%m-%d")
        end_str = (today + timezone.timedelta(days=2)).strftime("%Y-%m-%d")
        response = self.client.get(self.url, {"start_date": start_str, "end_date": end_str})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        results = data.get("results", {})
        
        # Verify delivered amount: 1000 - 100 = 900
        self.assertEqual(float(results.get("dashboard_breakdown", {}).get("delivered_amount", 0)), 900.0)
        
        # Verify total charge: 150 (delivery) + 50 (cancelled) = 200
        self.assertEqual(float(results.get("dashboard_breakdown", {}).get("total_charge", 0)), 200.0)
        
        # Verify statement details for today's date
        statement_list = results.get("statement", [])
        self.assertTrue(len(statement_list) >= 1)
        
        today_str = today.strftime("%Y-%m-%d")
        today_entry = next((entry for entry in statement_list if entry["date"] == today_str), None)
        self.assertIsNotNone(today_entry)
        
        # Delivery charge in statement should sum delivery + cancelled = 200
        self.assertEqual(float(today_entry["delivery_charge"]), 200.0)



