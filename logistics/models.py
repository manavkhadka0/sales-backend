from django.db import models

from account.models import CustomUser
from sales.models import Order

# Crete your models here.


class OrderChangeLog(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="change_logs"
    )
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, null=True, blank=True
    )
    old_status = models.CharField(max_length=255)
    new_status = models.CharField(max_length=255)
    comment = models.TextField(null=True, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["changed_at"]
        indexes = [
            models.Index(fields=["order", "changed_at"]),
            models.Index(fields=["user", "changed_at"]),
            models.Index(fields=["new_status", "changed_at"]),
        ]

    def __str__(self):
        return f"{self.order.order_code} - {self.old_status} → {self.new_status}"


class OrderComment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, null=True, blank=True
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["order", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.order.order_code} - {self.comment}"


class AssignOrder(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="assign_orders"
    )
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, null=True, blank=True
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_rider_verified = models.BooleanField(default=False)
    ydm_delivery_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Logistics delivery charge set by the rider based on delivery address (separate from franchise delivery_charge)",
    )

    DELIVERY_LOCATION_CHOICES = (
        ("Inside Ringroad", "Inside Ringroad"),
        ("Outside Ringroad", "Outside Ringroad"),
    )
    delivery_location_type = models.CharField(
        max_length=50,
        choices=DELIVERY_LOCATION_CHOICES,
        null=True,
        blank=True,
        db_index=True,
        help_text="Delivery location type selected by the rider (Inside Ringroad or Outside Ringroad).",
    )

    ydm_cancelled_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Logistics cancelled charge set when the order is assigned or updated (separate from franchise delivery_charge)",
    )

    class Meta:
        ordering = ["-assigned_at"]
        indexes = [
            models.Index(fields=["order", "-assigned_at"]),
            models.Index(fields=["user", "-assigned_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.order.order_code}"




class Invoice(models.Model):
    STATUS = (
        ("Draft", "Draft"),
        ("Partially Paid", "Partially Paid"),
        ("Pending", "Pending"),
        ("Paid", "Paid"),
    )
    PAYMENT_TYPE = (
        ("Cash", "Cash"),
        ("Bank Transfer", "Bank Transfer"),
        ("Cheque", "Cheque"),
    )
    franchise = models.ForeignKey(
        "account.Franchise", on_delete=models.CASCADE, related_name="invoices"
    )
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="created_invoices",
        null=True,
        blank=True,
    )
    invoice_code = models.CharField(max_length=255, null=True, blank=True)

    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    paid_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    due_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE, default="Cash")
    status = models.CharField(max_length=20, choices=STATUS, default="Draft")

    approved_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="approved_invoices",
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    is_approved = models.BooleanField(default=False)

    signature = models.FileField(upload_to="invoice_signatures/", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.invoice_code}"


class ReportInvoice(models.Model):
    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="report_invoices"
    )
    reported_by = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="report_invoices",
        null=True,
        blank=True,
    )
    comment = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["invoice", "-created_at"]),
            models.Index(fields=["reported_by", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.invoice.invoice_code} - {self.reported_by.username}"


class RiderCommissionRate(models.Model):
    order_min_amount = models.DecimalField(max_digits=10, decimal_places=2)
    order_max_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["order_min_amount"]

    def __str__(self):
        max_str = (
            f"{self.order_max_amount}" if self.order_max_amount is not None else "Above"
        )
        return f"Order Amount {self.order_min_amount} - {max_str} : Commission {self.commission_amount}"


class RiderPayout(models.Model):
    rider = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="rider_payouts",
        limit_choices_to={"role": "YDM_Rider"},
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_at = models.DateTimeField(auto_now_add=True)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-paid_at"]

    def __str__(self):
        return f"{self.rider.username} - {self.amount} on {self.paid_at.date()}"


class YdmLogisticsSetting(models.Model):
    inside_ringroad_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=100.00,
        help_text="YDM delivery charge for inside ringroad deliveries.",
    )
    outside_ringroad_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=150.00,
        help_text="YDM delivery charge for outside ringroad deliveries.",
    )
    cancelled_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="YDM charge for cancelled / returned deliveries.",
    )

    class Meta:
        verbose_name = "YDM Logistics Setting"
        verbose_name_plural = "YDM Logistics Settings"

    def __str__(self):
        return f"Inside: {self.inside_ringroad_charge}, Outside: {self.outside_ringroad_charge}, Cancelled: {self.cancelled_charge}"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # Prevent deletion of the singleton instance

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                "inside_ringroad_charge": 100.00,
                "outside_ringroad_charge": 150.00,
                "cancelled_charge": 0.00,
            },
        )
        return obj
