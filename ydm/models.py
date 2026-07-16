from django.db import models


class YDMLogistics(models.Model):
    franchise = models.OneToOneField(
        "account.Franchise",
        on_delete=models.CASCADE,
        related_name="ydm_logistics",
        null=True,
        blank=True,
    )
    api_key = models.CharField(max_length=255)

    class Meta:
        verbose_name = "YDM Logistics"
        verbose_name_plural = "YDM Logistics"

    def __str__(self):
        return f"{self.franchise} — {self.api_key}"
