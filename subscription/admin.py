from django.contrib import admin
from .models import Subscription

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """Subscription Admin"""
    list_display = ('user', 'subscribed_to', 'created_at')
    search_fields = ('user__email', 'subscribed_to__email')
    list_filter = ('created_at',)
    date_hierarchy = 'created_at'