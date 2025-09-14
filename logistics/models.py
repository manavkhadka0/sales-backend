from django.db import models
from account.models import CustomUser
from sales.models import Order
# Crete your models here.


class OrderChangeLog(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='change_logs')
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, null=True, blank=True)
    old_status = models.CharField(max_length=255)
    new_status = models.CharField(max_length=255)
    comment = models.TextField(null=True, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['changed_at']
        indexes = [
            models.Index(fields=['order', 'changed_at']),
            models.Index(fields=['user', 'changed_at']),
            models.Index(fields=['new_status', 'changed_at']),
        ]

    def __str__(self):
        return f"{self.order.order_code} - {self.old_status} → {self.new_status}"


class OrderComment(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, null=True, blank=True)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.order.order_code} - {self.comment}"


class AssignOrder(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='assign_orders')
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, null=True, blank=True)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-assigned_at']
        indexes = [
            models.Index(fields=['order', '-assigned_at']),
            models.Index(fields=['user', '-assigned_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.order.order_code}"


class FranchisePaymentLog(models.Model):
    """Track payments made by YDM to franchises"""
    franchise = models.ForeignKey(
        'account.Franchise', on_delete=models.CASCADE, related_name='payment_logs')
    paid_by = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE,
        limit_choices_to={'role__in': ['YDM_Logistics', 'YDM_Operator', 'SuperAdmin']})
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(
        max_length=50,
        choices=[
            ('cash', 'Cash'),
            ('bank_transfer', 'Bank Transfer'),
            ('cheque', 'Cheque'),
            ('digital_wallet', 'Digital Wallet'),
        ],
        default='cash'
    )
    notes = models.TextField(blank=True, null=True)
    payment_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['franchise', '-payment_date']),
            models.Index(fields=['paid_by', '-payment_date']),
        ]

    def __str__(self):
        return f"{self.franchise.name} - {self.amount_paid}"
