from django.db import models

# Create your models here.


class Report(models.Model):
    franchise = models.ForeignKey(
        "account.Franchise", on_delete=models.CASCADE, null=True, blank=True
    )
    message_received_fb = models.IntegerField(null=True, blank=True)
    message_received_whatsapp = models.IntegerField(null=True, blank=True)
    message_received_tiktok = models.IntegerField(null=True, blank=True)
    call_received = models.IntegerField(null=True, blank=True)
    customer_follow_up = models.IntegerField(null=True, blank=True)
    new_customer = models.IntegerField(null=True, blank=True)
    daily_dollar_spending = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    customer_to_package = models.IntegerField(null=True, blank=True)
    free_treatment = models.IntegerField(null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.franchise.name} - {self.created_at.strftime('%Y-%m-%d')}"
