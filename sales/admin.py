from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import *

# Register your models here.


class LocationAdmin(ModelAdmin):
    list_display = ["name", "coverage_areas"]
    list_filter = ["logistics"]
    search_fields = ["name", "coverage_areas"]


class OrderProductInline(TabularInline):
    model = OrderProduct
    extra = 1


class OrderAdmin(ModelAdmin):
    list_display = [
        "full_name",
        "date",
        "get_sales_person_name",
        "franchise__name",
        "product_name",
        "delivery_address",
        "phone_number",
        "payment_method",
        "total_amount",
        "prepaid_amount",
        "order_status",
        "logistics",
    ]
    list_filter = [
        "sales_person",
        "order_products__product__product",
        "order_status",
        "created_at",
        "franchise__name",
    ]
    search_fields = ["full_name", "phone_number", "sales_person__first_name"]
    autocomplete_fields = ["sales_person"]

    def get_sales_person_name(self, obj):
        return obj.sales_person.first_name

    get_sales_person_name.short_description = "Sales Person"

    def product_name(self, obj):
        return ", ".join(
            [
                f"{op.product.product.name} (Quantity: {op.quantity})"
                for op in obj.order_products.all()
            ]
        )

    product_name.short_description = "Product Name"

    inlines = [OrderProductInline]


class ProductAdmin(ModelAdmin):
    list_display = ["name", "id", "is_factory_ingredient", "status"]
    list_editable = ["is_factory_ingredient", "status"]


class InventoryAdmin(ModelAdmin):
    list_display = ["product", "id", "distributor", "franchise", "quantity"]
    list_filter = ["distributor", "franchise", "factory"]


class InventoryChangeLogAdmin(ModelAdmin):
    list_filter = ["changed_at"]


class InventoryRequestItemInline(TabularInline):
    model = InventoryRequestItem
    extra = 1


class InventoryRequestAdmin(ModelAdmin):
    list_display = ["franchise"]
    list_filter = ["franchise"]
    inlines = [InventoryRequestItemInline]


admin.site.register(Product, ProductAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(Inventory, InventoryAdmin)
admin.site.register(Commission, ModelAdmin)
admin.site.register(InventoryChangeLog, InventoryChangeLogAdmin)
admin.site.register(InventoryRequest, InventoryRequestAdmin)
admin.site.register(PromoCode, ModelAdmin)
admin.site.register(Location, LocationAdmin)

admin.site.register(DatabaseMode, ModelAdmin)
admin.site.register(HistoricalDataConfig, ModelAdmin)
