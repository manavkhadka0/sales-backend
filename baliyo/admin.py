from django.contrib import admin
from django.db import models
# Register your models here.
from .models import Project
from unfold.admin import ModelAdmin
from tinymce.widgets import TinyMCE

class TinyMce(ModelAdmin):
    formfield_overrides = {
        models.TextField: {'widget': TinyMCE()},
    }

admin.site.register(Project,TinyMce)