from django.contrib import admin
from unfold.admin import ModelAdmin

from tracking.models import SalesPersonLocation, SalesPersonLocationHistory


@admin.register(SalesPersonLocation)
class SalesPersonLocationAdmin(ModelAdmin):
    list_display = (
        "salesperson",
        "latitude",
        "longitude",
        "accuracy",
        "tracking_status",
        "is_online",
        "last_updated_at",
    )
    list_filter = ("is_online", "last_updated_at")
    search_fields = (
        "salesperson__username",
        "salesperson__first_name",
        "salesperson__last_name",
        "salesperson__phone_number",
    )
    ordering = ("-last_updated_at",)


@admin.register(SalesPersonLocationHistory)
class SalesPersonLocationHistoryAdmin(ModelAdmin):
    list_display = (
        "salesperson",
        "latitude",
        "longitude",
        "accuracy",
        "recorded_at",
        "created_at",
    )
    list_filter = ("created_at", "recorded_at")
    search_fields = (
        "salesperson__username",
        "salesperson__phone_number",
    )
    ordering = ("-created_at",)
