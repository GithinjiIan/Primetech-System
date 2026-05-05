"""
Admin configuration for Notifications.
"""
from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'notification_type', 'title', 'is_read', 'email_sent', 'created_at')
    list_filter = ('notification_type', 'is_read', 'email_sent')
    search_fields = ('title', 'message', 'recipient__email')
    readonly_fields = ('created_at', 'read_at')
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False  # Notifications are created programmatically
