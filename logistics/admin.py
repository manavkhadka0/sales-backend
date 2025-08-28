from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import OrderChangeLog, OrderComment, AssignOrder
# Register your models here.


class OrderChangeLogAdmin(ModelAdmin):
    list_display = ('order', 'user', 'old_status',
                    'new_status', 'comment', 'changed_at')
    list_filter = ('order', 'user', 'old_status', 'new_status', 'changed_at')
    search_fields = ('order', 'user', 'old_status', 'new_status', 'comment')
    ordering = ('-changed_at',)


admin.site.register(OrderChangeLog, OrderChangeLogAdmin)


class OrderCommentAdmin(ModelAdmin):
    list_display = ('order', 'user', 'comment', 'created_at', 'updated_at')
    list_filter = ('order', 'user', 'created_at', 'updated_at')
    search_fields = ('order', 'user', 'comment')
    ordering = ('-created_at',)


admin.site.register(OrderComment, OrderCommentAdmin)


class AssignOrderAdmin(ModelAdmin):
    list_display = ('order', 'user', 'assigned_at')
    list_filter = ('order', 'user', 'assigned_at')
    search_fields = ('order', 'user', 'assigned_at')
    ordering = ('-assigned_at',)


admin.site.register(AssignOrder, AssignOrderAdmin)
