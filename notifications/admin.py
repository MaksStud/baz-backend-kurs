from django.contrib import admin
from .models import Notification, CongratulatoryNotification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin interface for managing notifications."""
    list_display = ['message_en', 'send_at', 'created_at']
    ordering = ['send_at']
    filter_horizontal = ('users',)
    exclude = ['message', 'button', 'is_button', 'is_send_back']

    def has_add_permission(self, request):
        """Disallow adding new notifications."""
        return False

    def has_change_permission(self, request, obj=None):
        """Disallow editing notifications."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Disallow deleting notifications."""
        return False


@admin.register(CongratulatoryNotification)
class CongratulatoryNotificationAdmin(admin.ModelAdmin):
    """Admin interface for congratulatory notifications."""
    ordering = ['send_at']
    filter_horizontal = ['users']
    exclude = ['message',]





