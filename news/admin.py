from django.contrib import admin
from .models import News


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    """News admin"""
    list_display = ['slug', 'title', 'priority']
    search_fields = ['slug', 'title', 'wishes__name', 'priority']
    exclude = ('title', 'description')


