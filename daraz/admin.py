from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import DarazSellerStore


class DarazSellerStoreAdmin(ModelAdmin):
    list_display = (
        "franchise",
        "access_token_expires_at",
        "refresh_token_expires_at",
    )


admin.site.register(DarazSellerStore, DarazSellerStoreAdmin)
