from rest_framework import serializers
from .models import Notification, CongratulatoryNotification


class NotificationSerializers(serializers.ModelSerializer):
    """Notification Serializers."""
    class Meta:
        model = Notification
        fields = ['id', 'message_en', 'message_uk', 'button', 'is_button', 'users', 'send_at', 'is_send_back']
        read_only_fields = ['users', 'send_at']

    def create(self, validated_data):
        request = self.context.get('request')

        notification = Notification.objects.create(**validated_data)
        notification.users.add(request.user)
        return notification


class CongratulatoryNotificationSerializer(serializers.ModelSerializer):
    """Congratulatory Notification Serializers."""

    class Meta:
        model = CongratulatoryNotification
        fields = ['id', 'message_en', 'message_uk']
