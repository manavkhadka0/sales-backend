from django.contrib import admin

from .models import YDMLogistics


@admin.register(YDMLogistics)
class YDMLogisticsAdmin(admin.ModelAdmin):
    list_display = ["id", "franchise", "api_key"]
    list_select_related = ["franchise"]
    search_fields = ["franchise__name", "api_key"]
