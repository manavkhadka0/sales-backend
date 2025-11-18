from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import PickNDrop

# Register your models here.


class PickNDropAdmin(ModelAdmin):
    list_display = (
        "franchise",
        "email",
        "password",
        "client_key",
        "client_secret",
        "created_at",
        "updated_at",
    )


admin.site.register(PickNDrop, PickNDropAdmin)
