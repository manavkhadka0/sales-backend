from django.contrib import admin
from unfold.admin import ModelAdmin,TabularInline
from .models import *
# Register your models here.

class OrderProductInline(TabularInline):
    model = OrderProduct
    extra = 1
    

class OrderAdmin(ModelAdmin):
    list_display = ['full_name', 'sales_person', 'product_name','delivery_address','phone_number','payment_method','total_amount','order_status','created_at']
    list_filter = ['sales_person', 'order_products__product', 'order_status', 'created_at']

    def product_name(self, obj):
        return ", ".join([f"{op.product.name} (Quantity: {op.quantity})" for op in obj.order_products.all()])
    product_name.short_description = 'Product Name'

    inlines = [OrderProductInline]

class ProductAdmin(ModelAdmin):
    list_display = ['name', 'price']

class InventoryAdmin(ModelAdmin):
    list_display = ['product', 'distributor', 'quantity']
    list_filter = ['distributor']

admin.site.register(Product, ProductAdmin)
admin.site.register(Order,OrderAdmin)
admin.site.register(Inventory, InventoryAdmin)
admin.site.register(Commission,ModelAdmin)