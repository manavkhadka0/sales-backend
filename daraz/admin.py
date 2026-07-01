from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import DarazLocation, DarazSellerStore


class DarazSellerStoreAdmin(ModelAdmin):
    list_display = (
        "franchise",
        "shipper_warehouse_name",
        "shipper_seller_id",
        "origin_name",
    )


class DarazLocationAdmin(ModelAdmin):
    list_display = ("city", "l3_id", "area", "l4_id")
    search_fields = ("city", "area", "l4_id")
    list_filter = ("city",)


admin.site.register(DarazSellerStore, DarazSellerStoreAdmin)
admin.site.register(DarazLocation, DarazLocationAdmin)
