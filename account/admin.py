from django.contrib import admin
from unfold.admin import ModelAdmin
from django.contrib.auth.hashers import make_password

# Register your models here.
from .models import CustomUser, Distributor

# admin.site.register(CustomUser,ModelAdmin)
admin.site.register(Distributor,ModelAdmin)


class CustomUserAdmin(ModelAdmin):
    model = CustomUser
    
    def save_model(self, request, obj, form, change):
        if obj.password and not obj.password.startswith(('pbkdf2_sha256$', 'bcrypt$', 'argon2')):
            obj.password = make_password(obj.password)
        super().save_model(request, obj, form, change)

admin.site.register(CustomUser, CustomUserAdmin)
