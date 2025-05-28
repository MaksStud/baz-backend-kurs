from django.contrib import admin
from .models import Brand


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    """Registration in admin fot Brand"""
    list_display = ['display_nickname', 'priority']
    exclude = ('name', 'description')

    @admin.display(description='Nickname')
    def display_nickname(self, obj):
        return obj.nickname or "-"
