from django.contrib import admin
from unfold.admin import ModelAdmin
from django.contrib.auth.hashers import make_password

# Register your models here.
from .models import CustomUser, Distributor, Franchise, Factory, Logistics

# admin.site.register(CustomUser,ModelAdmin)


class FranchiseAdmin(ModelAdmin):
    model = Franchise
    list_display = ('name', 'id',)


class DistributorAdmin(ModelAdmin):
    model = Distributor
    list_display = ('name', 'id',)


admin.site.register(Distributor, DistributorAdmin)
admin.site.register(Franchise, FranchiseAdmin)
admin.site.register(Factory, ModelAdmin)
admin.site.register(Logistics, ModelAdmin)


class CustomUserAdmin(ModelAdmin):
    model = CustomUser
    list_display = ('first_name', 'phone_number', 'distributor__name',
                    'franchise__name', 'role', 'total_orders')  # Add other fields as necessary
    list_filter = ('role', 'distributor__name')

    def total_orders(self, obj):
        return obj.orders.count()  # Count the related orders for the user
    # Optional: Set a short description for the column
    total_orders.short_description = 'Total Orders'

    def save_model(self, request, obj, form, change):
        if obj.password and not obj.password.startswith(('pbkdf2_sha256$', 'bcrypt$', 'argon2')):
            obj.password = make_password(obj.password)
        super().save_model(request, obj, form, change)


admin.site.register(CustomUser, CustomUserAdmin)
