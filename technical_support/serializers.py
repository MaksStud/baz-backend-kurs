from rest_framework import serializers
from .models import TechnicalSupportChatMessage, TechnicalSupportChat
from user.serializers import ReturnBazhayUserSerializer


class TechnicalSupportChatMessageSerializer(serializers.ModelSerializer):
    """Technical support chat message serializer."""

    class Meta:
        model = TechnicalSupportChatMessage
        fields = ['id', 'message_text', 'created_at', 'from_user', 'file']
        read_only_fields = ['id']


class TechnicalSupportChatSerializer(serializers.ModelSerializer):
    """Technical support chat serializer."""
    bazhay_user = ReturnBazhayUserSerializer(read_only=True)
    messages = TechnicalSupportChatMessageSerializer(many=True, read_only=True, source='chat_message')

    class Meta:
        model = TechnicalSupportChat
        fields = ['id', 'title', 'bazhay_user', 'messages']
