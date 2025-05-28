import datetime
import requests
from django.utils import timezone

from django.conf import settings

from rest_framework.serializers import ValidationError

from google.oauth2 import service_account
from google.auth.transport.requests import Request

from .servicer_abstract_factory import CompanyPaymentValidateAbstract

root_path = settings.BASE_DIR


class GooglePaymentValidation(CompanyPaymentValidateAbstract):
    """A service for checking payment via Google."""

    def end_date(self, payment_code: dict) -> datetime:
        """"""
        payment_data = self.get_payment_data(payment_code)

        payment_state = payment_data.get('paymentState')
        if payment_state == 1 or payment_state == 2:
            data = int(payment_data.get('expiryTimeMillis')) / 1000
            naive_datetime = datetime.datetime.fromtimestamp(data)
            return timezone.make_aware(naive_datetime)
        else:
            raise ValidationError(detail="Code status in invalid.")

    def subscription_time_type(self, payment_code: dict) -> str:
        payment_data = self.get_payment_data(payment_code)
        start_time_millis = payment_data.get('startTimeMillis')
        expiry_time_millis = payment_data.get('expiryTimeMillis')

        if not start_time_millis or not expiry_time_millis:
            raise ValidationError(detail="Invalid or missing time values")

        try:
            start_time_seconds = int(start_time_millis) / 1000.0
            expiry_time_seconds = int(expiry_time_millis) / 1000.0

            start_time = datetime.datetime.fromtimestamp(start_time_seconds)
            expiry_time = datetime.datetime.fromtimestamp(expiry_time_seconds)

            delta_time = expiry_time - start_time

            if delta_time.days <= 7:
                return 'try'
            elif delta_time.days <= 30:
                return 'monthly'
            elif delta_time.days <= 365:
                return 'yearly'
            else:
                raise ValidationError(detail="Error while processing time data")
        except (TypeError, ValueError):
            raise ValidationError(detail="Error while processing time data")

    def get_payment_data(self, payment_code) -> dict:
        service_account_file = str(
            root_path) + '/premium/services/google_certificates/meta-tracker-304410-8b1ff946e12e.json'

        credentials = service_account.Credentials.from_service_account_file(
            service_account_file,
            scopes=['https://www.googleapis.com/auth/androidpublisher']
        )

        credentials.refresh(Request())

        PACKAGE_NAME = payment_code.get('package_name')
        PRODUCT_ID = payment_code.get('product_id')
        PURCHASE_TOKEN = payment_code.get('purchase_token')

        headers = {'Authorization': f'Bearer {credentials.token}'}
        url = f'https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{PACKAGE_NAME}/purchases/subscriptions/{PRODUCT_ID}/tokens/{PURCHASE_TOKEN}'

        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise ValidationError(detail=f"Google service error: status {response.status_code}, message: {response.text}.")