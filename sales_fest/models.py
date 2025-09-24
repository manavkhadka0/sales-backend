from django.db import models

from account.models import CustomUser, Franchise
from lucky_draw.models import LuckyDrawSystem

# Create your models here.


class FestConfig(models.Model):
    franchise = models.ForeignKey(
        Franchise, on_delete=models.CASCADE, null=True, blank=True
    )
    has_lucky_draw = models.BooleanField(default=False)
    lucky_draw_system = models.ForeignKey(
        LuckyDrawSystem,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    has_sales_fest = models.BooleanField(default=False)
    sales_group = models.ManyToManyField("sales_fest.SalesGroup", blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["franchise"], name="unique_franchise_fest_config"
            )
        ]

    def __str__(self):
        return self.franchise.name if self.franchise else "Global"


class SalesGroup(models.Model):
    group_name = models.CharField(max_length=255)
    leader = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="sales_group",
        null=True,
        blank=True,
    )
    members = models.ManyToManyField(
        CustomUser, related_name="sales_group_members", blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.group_name
