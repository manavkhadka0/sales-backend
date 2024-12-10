from django.contrib import admin
from unfold.admin import ModelAdmin

# Register your models here.
from .models import CustomUser, Distributor

# admin.site.register(CustomUser,ModelAdmin)
admin.site.register(Distributor,ModelAdmin)


class CustomUserAdmin(ModelAdmin):
    model = CustomUser

    def save_model(self, request, obj, form, change):
        if 'password' in form.cleaned_data:  # Check if password is provided
            raw_password = form.cleaned_data['password']
            obj.set_password(raw_password)  # Hash the password
        super().save_model(request, obj, form, change)

admin.site.register(CustomUser, CustomUserAdmin)
