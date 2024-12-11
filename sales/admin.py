from django.contrib import admin
from unfold.admin import ModelAdmin,TabularInline
from .models import *
# Register your models here.

class OrderProductInline(TabularInline):
    model = OrderProduct
    extra = 1

class OrderAdmin(ModelAdmin):
    inlines = [OrderProductInline]

admin.site.register(Product,ModelAdmin)
admin.site.register(Order,OrderAdmin)
admin.site.register(Inventory,ModelAdmin)
admin.site.register(Commission,ModelAdmin)