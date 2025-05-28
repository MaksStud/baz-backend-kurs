from django.contrib import admin
from .models import Premium


@admin.register(Premium)
class PremiumAdmin(admin.ModelAdmin):
    """Admin interface for Premium model."""
    list_display = ['bazhay_user', 'end_date', 'is_an_annual_payment', 'is_trial_period']
    autocomplete_fields = ['bazhay_user']
