from django.contrib import admin
from unfold.admin import ModelAdmin

# Register your models here.
from .models import CustomUser, Distributor

admin.site.register(CustomUser,ModelAdmin)
admin.site.register(Distributor,ModelAdmin)


