from django.contrib import admin
from django.urls import path, reverse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.html import format_html
from django.http import JsonResponse

from .models import TechnicalSupportEmail, TechnicalSupportChat, TechnicalSupportChatMessage


@admin.register(TechnicalSupportEmail)
class TechnicalSupportEmailAdmin(admin.ModelAdmin):
    list_display = ('admin_email',)


class TechnicalSupportChatMessageInline(admin.TabularInline):
    """In line register technical support chat message."""
    model = TechnicalSupportChatMessage
    extra = 1


@admin.register(TechnicalSupportChat)
class TechnicalSupportChatAdmin(admin.ModelAdmin):
    list_display = ['bazhay_user', 'title', 'last_action_time', 'is_active', 'chat_link']
    inlines = [TechnicalSupportChatMessageInline]

    def chat_link(self, obj):
        """Provide a link to the custom chat view."""
        url = reverse('technical_support:technical_support_chat_in_admin', args=[obj.id])
        return format_html('<a href="{}">Go to chat</a>', url)
    chat_link.short_description = "Chat"