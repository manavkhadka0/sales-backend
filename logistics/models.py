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
