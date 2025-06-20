from django.contrib import admin
from .models import Dash
from unfold.admin import ModelAdmin
# Register your models here.


@admin.register(Dash)
class DashAdmin(ModelAdmin):
    list_display = ['email', 'franchise', 'created_at', 'updated_at']
    search_fields = ['email', 'franchise__name']
    list_filter = ['created_at', 'updated_at']
    readonly_fields = ['created_at', 'updated_at']
