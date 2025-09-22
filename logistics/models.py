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
