# models.py
from django.db import models

from account.models import Franchise


class DarazSellerStore(models.Model):
    # Link it to your app's user if necessary
    franchise = models.ForeignKey(Franchise, on_delete=models.CASCADE)

    # Origin details
    origin_name = models.CharField(max_length=255, null=True, blank=True)
    origin_phone = models.CharField(max_length=20, null=True, blank=True)
    origin_email = models.EmailField(max_length=255, null=True, blank=True)
    origin_address_city = models.CharField(max_length=255, null=True, blank=True)
    origin_address_id = models.CharField(max_length=100, null=True, blank=True)
    origin_address_details = models.CharField(max_length=500, null=True, blank=True)
    origin_address_type = models.CharField(max_length=50, default="work")

    # Shipper details
    shipper_seller_id = models.CharField(max_length=255, null=True, blank=True)
    shipper_platform_name = models.CharField(max_length=255, null=True, blank=True)
    shipper_external_warehouse_code = models.CharField(
        max_length=100, null=True, blank=True
    )
    shipper_warehouse_name = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.franchise.name} - {self.shipper_warehouse_name}"


class DarazLocation(models.Model):
    city = models.CharField(max_length=255, db_index=True)
    l3_id = models.CharField(max_length=100, null=True, blank=True)
    area = models.CharField(max_length=255, db_index=True)
    l4_id = models.CharField(max_length=100, unique=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Daraz Location"
        verbose_name_plural = "Daraz Locations"
        ordering = ["city", "area"]

    def __str__(self):
        return f"{self.city} - {self.area} ({self.l4_id})"
