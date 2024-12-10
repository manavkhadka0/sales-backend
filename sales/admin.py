from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import *
# Register your models here.

admin.site.register(Product,ModelAdmin)
admin.site.register(Order,ModelAdmin)
admin.site.register(OrderProduct,ModelAdmin)
admin.site.register(Inventory,ModelAdmin)