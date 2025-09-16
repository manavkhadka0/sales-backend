from django.contrib import admin
from unfold.admin import ModelAdmin
from . models import *
from tinymce.widgets import TinyMCE
# Register your models here.

admin.site.register(Organization, ModelAdmin)


class GiftItemAdmin(ModelAdmin):
    search_fields = ['name']  # or whichever fields should be searchable


admin.site.register(GiftItem, GiftItemAdmin)


class LuckyDrawSystemAdmin(ModelAdmin):
    formfield_overrides = {
        models.TextField: {'widget': TinyMCE, },
    }


admin.site.register(LuckyDrawSystem, LuckyDrawSystemAdmin)

admin.site.register(Sales, ModelAdmin)
admin.site.register(RechargeCard, ModelAdmin)
admin.site.register(RechargeCardOffer, ModelAdmin)
admin.site.register(FixOffer, ModelAdmin)


admin.site.register(MobilePhoneOffer, ModelAdmin)


class IMEIAdmin(ModelAdmin):
    search_fields = ('imei_no',)


admin.site.register(IMEINO, IMEIAdmin)


class CustomerAdmin(ModelAdmin):
    list_display = (
        'full_name',
        'prize_details',
        'date_of_purchase',
    )


admin.site.register(Customer, CustomerAdmin)
admin.site.register(MobileOfferCondition, ModelAdmin)
admin.site.register(RechargeCardCondition, ModelAdmin)
admin.site.register(ElectronicOfferCondition, ModelAdmin)


class ElectronicsShopOfferAdmin(ModelAdmin):
    list_display = (
        'type_of_offer',
        'get_gifts',  # custom method
        'lucky_draw_system',
        'offer_condition_value',
        'daily_quantity',
        'start_date',
        'end_date',
    )
    autocomplete_fields = ['gift']  # <--- searchable dropdown for gifts

    def get_gifts(self, obj):
        # Join names of related gifts into a string
        return ", ".join([str(g) for g in obj.gift.all()])

    get_gifts.short_description = "Gifts"


admin.site.register(ElectronicsShopOffer, ElectronicsShopOfferAdmin)
