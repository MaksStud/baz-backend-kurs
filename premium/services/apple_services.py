import datetime
import logging

from django.conf import settings

from rest_framework.serializers import ValidationError

from .servicer_abstract_factory import CompanyPaymentValidateAbstract

from appstoreserverlibrary.api_client import AppStoreServerAPIClient
from appstoreserverlibrary.receipt_utility import ReceiptUtility
from appstoreserverlibrary.signed_data_verifier import SignedDataVerifier
from appstoreserverlibrary.models.Environment import Environment

logger = logging.getLogger(__name__)

root_path = settings.BASE_DIR


class ApplePaymentValidation(CompanyPaymentValidateAbstract):
    """Service for payment validation with Apple."""
    def __init__(self):
        self.app_apple_key_id = settings.APPLE_KEY_ID
        self.issuer_id = settings.APPLE_ISSUER_ID
        self.bundle_id = settings.APPLE_BUNDLE_ID
        self.environments = [Environment.PRODUCTION, Environment.SANDBOX]

    def __read_private_key(self):
        """Reads the key from a file and returns it."""
        path = str(root_path) + '/premium/services/apple_certificates/AuthKey_F74XYY2WSM.p8'
        with open(path, 'rb') as f:
            private_key = f.read()

        return private_key

    def __load_root_certificates(self):
        """Returns a list of absolute paths to certificates."""
        file_names = ["AppleComputerRootCertificate.cer", "AppleIncRootCertificate.cer",
                      "AppleRootCA-G2.cer", "AppleRootCA-G3.cer"]
        cert_list = []
        path = str(root_path) + '/premium/services/apple_certificates/'

        for file_name in file_names:
            cert_file_path = path + file_name
            with open(cert_file_path, 'rb') as f:
                cert_list.append(f.read())
        return cert_list

    def end_date(self, app_receipt) -> datetime:
        """
        Receives all payment data. Returns the time until which the subscription should be valid.
        :param app_receipt: String for retrieval data about payment.
        """
        receipt_util = ReceiptUtility()
        private_key = self.__read_private_key()
        root_certificates = self.__load_root_certificates()

        try:
            transaction_info = self.get_transaction_info(private_key, receipt_util, app_receipt)

            return self.verify_transaction_and_get_date(root_certificates, transaction_info)
        except Exception as e:
            raise ValidationError(detail=f'{e}')

    def get_transaction_info(self, private_key, receipt_util, app_receipt):
        """
        Tries to reject a transaction with different clients.

        :param private_key: Private key for access.
        :param receipt_util: object ReceiptUtility
        :param app_receipt: String for retrieval data about payment.

        :return: Transaction data or nothing.
        """
        for environment in self.environments:
            client = AppStoreServerAPIClient(
                private_key,
                self.app_apple_key_id,
                self.issuer_id,
                self.bundle_id,
                environment
            )
            try:
                return self.get_transaction(receipt_util, app_receipt, client)
            except Exception as e:
                logger.error(f"Error in environment {environment}: {e}")
                continue

    def verify_transaction_and_get_date(self, root_certificates, transaction_info):
        """
        Decrypts transaction data and return data expiration date.

        :param root_certificates: Private key for access.
        :param transaction_info: object ReceiptUtility

        :return: Subscription expiration date.
        """
        for environment in self.environments:
            try:
                signed_data_verifier = SignedDataVerifier(
                    root_certificates,
                    True,
                    environment,
                    self.bundle_id,
                    self.app_apple_key_id
                )
                payment_info = signed_data_verifier.verify_and_decode_signed_transaction(
                    transaction_info.signedTransactionInfo
                )
                purchase_date = payment_info.purchaseDate / 1000
                return datetime.datetime.fromtimestamp(purchase_date)
            except Exception as e:
                logger.error(f"Error verifying transaction in environment {environment}: {e}")
                continue

    def get_transaction(self, receipt_util, app_receipt, client):
        """
        Gets the transaction data by its id.

        :param receipt_util: object ReceiptUtility.
        :param app_receipt: String for retrieval data about payment.
        :param client: Client apple.

        :return: Transaction info or nothing.
        """
        transaction_id = receipt_util.extract_transaction_id_from_app_receipt(app_receipt)
        return client.get_transaction_info(transaction_id)
