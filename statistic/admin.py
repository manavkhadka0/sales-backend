from django.contrib import admin
from .models import Report
from unfold.admin import ModelAdmin

# Register your models here.
@admin.register(Report)
class ReportAdmin(ModelAdmin):
    list_display = [
        "franchise",
        "reported_by",
        'date',
        'created_at',
        'updated_at'
    ]
    model = Report

