from django.core.cache import cache

from rest_framework import serializers
import datetime

from .models import Premium
from .services.apple_services import ApplePaymentValidation
from .services.google_service import GooglePaymentValidation


class BaseValidateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Premium
        fields = ['id', 'end_date', 'is_an_annual_payment', 'is_trial_period']
        read_only_fields = ['id', 'end_date']

    def create(self, validated_data):
        """Creates a premium or updates a premium for a user."""
        premium, created = Premium.objects.get_or_create(bazhay_user=self.context['request'].user)
        premium.end_date = self.get_end_date(validated_data)

        user = self.context.get('request').user
        cache_keys = [f'premium_to_{user.id}', f'profile_{user.id}']
        for cache_key in cache_keys:
            cache.delete(cache_key)

        premium.save()
        return premium

    def get_services(self):
        """An abstract method for obtaining a validation service. Each specific class must implement this method."""
        raise NotImplementedError("You should implement get_services method")

    def get_end_date(self, validated_data):
        """
        Abstract method for obtaining the date of prepayment completion.
        Each specific class must implement this method.
        """
        raise NotImplementedError("You should implement get_end_date method")


class GoogleValidateSerializer(BaseValidateSerializer):
    """Serializer to validate and create premium for user with Google payment system."""
    package_name = serializers.CharField(write_only=True)
    product_id = serializers.CharField(write_only=True)
    purchase_token = serializers.CharField(write_only=True)

    class Meta(BaseValidateSerializer.Meta):
        fields = BaseValidateSerializer.Meta.fields + ['package_name', 'product_id', 'purchase_token']

    def get_services(self):
        """A method for transferring a service."""
        return GooglePaymentValidation()

    def get_end_date(self, validated_data):
        """
        Receives the premium expiration time from the service.
        :param validated_data: Dictionary with data to get the date.
        """
        return self.get_services().end_date(validated_data)

    def create(self, validated_data):
        """Creates a premium or updates a premium for a user."""
        premium = super().create(validated_data)
        time_type = self.get_services().subscription_time_type(validated_data)

        match time_type:
            case 'try':
                premium.is_trial_period = True
                premium.is_an_annual_payment = False
            case 'yearly':
                premium.is_trial_period = False
                premium.is_an_annual_payment = True
            case 'monthly':
                premium.is_an_annual_payment = False
                premium.is_trial_period = False
        premium.save()
        return premium


class AppleValidateSerializer(BaseValidateSerializer):
    """Serializer to validate and create premium for user with Apple payment system."""
    app_receipt = serializers.CharField(write_only=True)

    class Meta(BaseValidateSerializer.Meta):
        fields = BaseValidateSerializer.Meta.fields + ['app_receipt']

    def get_services(self):
        """A method for transferring a service."""
        return ApplePaymentValidation()

    def get_end_date(self, validated_data) -> datetime.datetime:
        """
        Receives the premium expiration time from the service.
        :param validated_data: Dictionary with data to get the date.
        """
        return self.get_services().end_date(validated_data.get('app_receipt'))

    def create(self, validated_data):
        premium = super().create(validated_data)

        premium.is_an_annual_payment = validated_data.get('is_an_annual_payment', False)
        premium.is_trial_period = validated_data.get('is_trial_period', False)

        date = self.get_end_date(validated_data)
        if validated_data.get('is_an_annual_payment'):
            premium.end_date = date + datetime.timedelta(days=365)
        elif validated_data.get('is_trial_period'):
            premium.end_date = date + datetime.timedelta(days=7)
        else:
            premium.end_date = date + datetime.timedelta(days=30)
        premium.save()
        return premium

