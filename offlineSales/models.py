import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from core.utils.s3bucket import PublicMediaStorage


def generate_offline_order_id():
    """
    Generate unique offline order code.
    Format: OFF-XXXXXXXX
    """
    uuid_str = str(uuid.uuid4()).replace("-", "").upper()
    return f"ORD-{uuid_str[:8]}"


class OfflineCustomer(models.Model):
    franchise = models.ForeignKey(
        "account.Franchise",
        on_delete=models.CASCADE,
        related_name="offline_customers",
        db_index=True,
        null=True,
        blank=True,
    )
    sales_person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="offline_customers",
        db_index=True,
    )
    store_name = models.CharField(max_length=255, db_index=True)
    contact_person = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, db_index=True)
    address = models.TextField()
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["franchise", "store_name"]),
            models.Index(fields=["franchise", "created_at"]),
            models.Index(fields=["sales_person", "created_at"]),
        ]

    def __str__(self):
        return f"{self.store_name} ({self.contact_person}) - {self.phone_number}"

    @property
    def total_orders_count(self):
        return self.orders.exclude(order_status="Cancelled").count()

    @property
    def total_purchased_amount(self):
        total = self.orders.exclude(order_status="Cancelled").aggregate(
            total=Sum("total_amount")
        )["total"]
        return total or Decimal("0.00")

    @property
    def total_paid_amount(self):
        total = (
            self.payment_history.model.objects.filter(
                models.Q(customer=self) | models.Q(order__customer=self)
            )
            .exclude(order__order_status="Cancelled")
            .aggregate(total=Sum("amount"))["total"]
        )
        return total or Decimal("0.00")

    @property
    def total_remaining_amount(self):
        purchased = self.total_purchased_amount
        paid = self.total_paid_amount
        return max(Decimal("0.00"), purchased - paid)


class OfflineOrder(models.Model):
    class OrderStatus(models.TextChoices):
        PENDING = "Pending", "Pending"
        CONFIRMED = "Confirmed", "Confirmed"
        DELIVERED = "Delivered", "Delivered"
        CANCELLED = "Cancelled", "Cancelled"

    class PaymentStatus(models.TextChoices):
        UNPAID = "Unpaid", "Unpaid (Credit)"
        PARTIAL = "Partial", "Partially Paid"
        PAID = "Paid", "Paid"

    order_code = models.CharField(
        max_length=50,
        unique=True,
        default=generate_offline_order_id,
        db_index=True,
    )
    franchise = models.ForeignKey(
        "account.Franchise",
        on_delete=models.CASCADE,
        related_name="offline_orders",
        db_index=True,
    )
    sales_person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="offline_orders",
        db_index=True,
    )
    customer = models.ForeignKey(
        OfflineCustomer,
        on_delete=models.CASCADE,
        related_name="orders",
        db_index=True,
    )
    order_date = models.DateField(default=timezone.localdate, db_index=True)
    order_status = models.CharField(
        max_length=50,
        choices=OrderStatus.choices,
        default=OrderStatus.DELIVERED,
        db_index=True,
    )
    payment_status = models.CharField(
        max_length=50,
        choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID,
        db_index=True,
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    paid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    remaining_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["franchise", "order_status"]),
            models.Index(fields=["franchise", "payment_status"]),
            models.Index(fields=["customer", "payment_status"]),
            models.Index(fields=["sales_person", "order_date"]),
            models.Index(fields=["order_date", "franchise"]),
        ]

    def __str__(self):
        return f"{self.order_code} - {self.customer.store_name} ({self.payment_status})"

    def recalculate_payment_status(self):
        """Update remaining amount and payment status based on paid vs total."""
        self.remaining_amount = max(
            Decimal("0.00"), self.total_amount - self.paid_amount
        )
        if self.remaining_amount == Decimal("0.00") and self.total_amount > Decimal(
            "0.00"
        ):
            self.payment_status = self.PaymentStatus.PAID
        elif self.paid_amount > Decimal("0.00"):
            self.payment_status = self.PaymentStatus.PARTIAL
        else:
            self.payment_status = self.PaymentStatus.UNPAID


class OfflineOrderItem(models.Model):
    order = models.ForeignKey(
        OfflineOrder,
        on_delete=models.CASCADE,
        related_name="items",
    )
    inventory = models.ForeignKey(
        "sales.Inventory",
        on_delete=models.PROTECT,
        related_name="offline_order_items",
    )
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        indexes = [
            models.Index(fields=["order", "inventory"]),
        ]

    def __str__(self):
        return f"{self.inventory.product.name} x {self.quantity}"


class OfflinePaymentHistory(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        ONLINE = "online", "Online / QR"
        CHEQUE = "cheque", "Cheque"
        BANK_TRANSFER = "bank_transfer", "Bank Transfer"

    customer = models.ForeignKey(
        OfflineCustomer,
        on_delete=models.CASCADE,
        related_name="payment_history",
        db_index=True,
        null=True,
        blank=True,
    )
    order = models.ForeignKey(
        OfflineOrder,
        on_delete=models.CASCADE,
        related_name="payment_history",
        db_index=True,
        null=True,
        blank=True,
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(
        max_length=50,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
        db_index=True,
    )
    payment_date = models.DateTimeField(default=timezone.now, db_index=True)
    payment_screenshot = models.FileField(
        upload_to="offline_sales/payments/",
        null=True,
        blank=True,
        storage=PublicMediaStorage(),
    )
    remarks = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_offline_payments",
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-payment_date"]
        indexes = [
            models.Index(fields=["customer", "payment_date"]),
            models.Index(fields=["order", "payment_date"]),
            models.Index(fields=["recorded_by", "payment_date"]),
        ]

    def save(self, *args, **kwargs):
        if not self.customer and self.order and self.order.customer:
            self.customer = self.order.customer
        super().save(*args, **kwargs)

    def __str__(self):
        target = (
            self.order.order_code
            if self.order
            else (self.customer.store_name if self.customer else "N/A")
        )
        return f"{target} - Rs. {self.amount} via {self.get_payment_method_display()}"
