from django.contrib import admin
from unfold.admin import ModelAdmin
from django.contrib.auth.hashers import make_password

# Register your models here.
from .models import CustomUser, Distributor,Franchise,Factory

# admin.site.register(CustomUser,ModelAdmin)
admin.site.register(Distributor,ModelAdmin)
admin.site.register(Franchise,ModelAdmin)
admin.site.register(Factory,ModelAdmin)


class CustomUserAdmin(ModelAdmin):
    model = CustomUser
    list_display = ('username','phone_number','distributor__name','franchise__name','role', 'total_orders')  # Add other fields as necessary
    list_filter = ('role','distributor__name')
    def total_orders(self, obj):
        return obj.orders.count()  # Count the related orders for the user
    total_orders.short_description = 'Total Orders'  # Optional: Set a short description for the column

    def save_model(self, request, obj, form, change):
        if obj.password and not obj.password.startswith(('pbkdf2_sha256$', 'bcrypt$', 'argon2')):
            obj.password = make_password(obj.password)
        super().save_model(request, obj, form, change)

admin.site.register(CustomUser, CustomUserAdmin)
