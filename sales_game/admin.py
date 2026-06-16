from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import Game, GameCondition, GameConditionRule, GameWinner


class GameConditionRuleInline(TabularInline):
    model = GameConditionRule
    extra = 1


class GameConditionAdmin(ModelAdmin):
    list_display = ["__str__", "game", "is_active", "created_at"]
    list_filter = ["game", "is_active"]
    search_fields = ["description"]
    inlines = [GameConditionRuleInline]


class GameAdmin(ModelAdmin):
    list_display = ["name", "active_condition", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name"]


class GameWinnerAdmin(ModelAdmin):
    list_display = ["order", "game", "condition", "won_at", "notified"]
    list_filter = ["game", "condition", "notified", "won_at"]
    search_fields = ["order__order_code", "order__full_name", "message"]


admin.site.register(Game, GameAdmin)
admin.site.register(GameCondition, GameConditionAdmin)
admin.site.register(GameWinner, GameWinnerAdmin)
