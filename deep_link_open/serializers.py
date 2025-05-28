import json
from rest_framework import serializers
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class AppleRedirectSerializer(serializers.Serializer):
    """Apple redirect Serializer."""
    @staticmethod
    def get_data():
        """Return data from file."""
        with open(settings.APPLE_REDIRECT_FILE_PATH, encoding="utf-8") as file:
            data = json.load(file)
            logger.info(data)
            return data


class PlayStoreSerializer(serializers.Serializer):
    """PlayStore Serializer."""
    file_content = serializers.JSONField()

    @staticmethod
    def get_data():
        """Return file."""
        file_path = settings.PLAY_STORE_FILE_PATH
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
