from rest_framework import serializers
from .models import Subscription
from user.serializers import ReturnBazhayUserSerializer
from user.models import BazhayUser


class CreateOrDeleteSubscriptionSerializer(serializers.ModelSerializer):
    """Subscription serializer"""
    user = ReturnBazhayUserSerializer(read_only=True)
    subscribed_to = ReturnBazhayUserSerializer(read_only=True)
    subscribed_to_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Subscription
        fields = ['user', 'subscribed_to', 'subscribed_to_id', 'created_at']

    def validate(self, data: dict) -> dict:
        """validate data"""
        subscribed_to_id = data.get('subscribed_to_id')
        request_user = self.context['request'].user

        try:
            subscribed_to_user = BazhayUser.objects.get(id=subscribed_to_id)
        except BazhayUser.DoesNotExist:
            raise serializers.ValidationError(detail="User not found.")

        if subscribed_to_user == request_user:
            raise serializers.ValidationError(detail="You cannot subscribe to yourself.")

        data['subscribed_to'] = subscribed_to_user
        return data

    def create(self, validated_data: dict) -> Subscription:
        """Create or get subscription"""
        user = self.context['request'].user
        subscribed_to = validated_data['subscribed_to']
        subscription, created = Subscription.objects.get_or_create(user=user, subscribed_to=subscribed_to)

        if not created:
            raise serializers.ValidationError({"detail": "You are already subscribed to this user."})

        return subscription

    def delete(self) -> Subscription:
        """Delete subscription"""
        user = self.context['request'].user
        subscribed_to = self.validated_data['subscribed_to']
        subscription = Subscription.objects.filter(user=user, subscribed_to=subscribed_to).first()

        if not subscription:
            raise serializers.ValidationError({"detail": "You are not subscribed to this user."})

        subscription.delete()
        return subscription


class SubscribersSerializer(serializers.ModelSerializer):
    user = ReturnBazhayUserSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = ['id', 'user']


class SubscriptionsSerializer(serializers.ModelSerializer):
    subscribed_to = ReturnBazhayUserSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = ['id', 'subscribed_to']

