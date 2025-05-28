from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import BazhayUser, Address, PostAddress, AccessToAddress, AccessToPostAddress, UserExponentPushToken


class BazhayUserAdmin(UserAdmin):
    """
    Custom admin interface for the BazhayUser model.
    """
    model = BazhayUser
    list_display = ('email', 'username', 'first_name', 'last_name')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    list_filter = ('is_active', 'is_staff', 'is_superuser')
    ordering = ('email',)


class UserExponentPushTokenAdmin(admin.ModelAdmin):
    search_fields = ['bazhay_user__email', 'token', 'imei', 'language']
    list_display = ['bazhay_user_email', 'token', 'imei', 'language']

    def bazhay_user_email(self, obj):
        return obj.bazhay_user.email if obj.bazhay_user else None

    bazhay_user_email.admin_order_field = 'bazhay_user__email'
    bazhay_user_email.short_description = 'User Email'


# Register the custom admin interface with the Django admin site
admin.site.register(BazhayUser, BazhayUserAdmin)
admin.site.register(Address)
admin.site.register(PostAddress)
admin.site.register(AccessToAddress)
admin.site.register(AccessToPostAddress)
admin.site.register(UserExponentPushToken, UserExponentPushTokenAdmin)
