from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import FestConfig, SalesGroup

# Register your models here.

admin.site.register(FestConfig, ModelAdmin)
admin.site.register(SalesGroup, ModelAdmin)
