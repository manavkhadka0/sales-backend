from django.contrib import admin
from django.db import models
from tinymce.widgets import TinyMCE
from unfold.admin import ModelAdmin

from .models import (
    Customer,
    FixOffer,
    GiftItem,
    LuckyDrawSystem,
    Offer,
    OfferCondition,
    Organization,
    Sales,
)

# Register your models here.

admin.site.register(Organization, ModelAdmin)


class GiftItemAdmin(ModelAdmin):
    search_fields = ["name"]  # or whichever fields should be searchable


admin.site.register(GiftItem, GiftItemAdmin)


class LuckyDrawSystemAdmin(ModelAdmin):
    formfield_overrides = {
        models.TextField: {
            "widget": TinyMCE,
        },
    }


admin.site.register(LuckyDrawSystem, LuckyDrawSystemAdmin)

admin.site.register(Sales, ModelAdmin)
admin.site.register(FixOffer, ModelAdmin)


class CustomerAdmin(ModelAdmin):
    list_display = (
        "full_name",
        "prize_details",
        "date_of_purchase",
    )


admin.site.register(Customer, CustomerAdmin)
admin.site.register(OfferCondition, ModelAdmin)


class OfferAdmin(ModelAdmin):
    list_display = (
        "type_of_offer",
        "get_gifts",  # custom method
        "lucky_draw_system",
        "offer_condition_value",
        "daily_quantity",
        "start_date",
        "end_date",
    )
    autocomplete_fields = ["gift"]  # <--- searchable dropdown for gifts

    def get_gifts(self, obj):
        # Join names of related gifts into a string
        return ", ".join([str(g) for g in obj.gift.all()])

    get_gifts.short_description = "Gifts"


admin.site.register(Offer, OfferAdmin)
