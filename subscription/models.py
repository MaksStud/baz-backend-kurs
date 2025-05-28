from django.db import models
from user.models import BazhayUser


class Subscription(models.Model):
    """Subscription model"""
    user = models.ForeignKey(BazhayUser, related_name='subscriptions', on_delete=models.CASCADE)
    subscribed_to = models.ForeignKey(BazhayUser, related_name='subscribers', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'subscribed_to')

    def __str__(self) -> str:
        return f"{self.user.email} subscribed to {self.subscribed_to.email}"

    @staticmethod
    def is_subscribed(user, subscribed_to):
        return Subscription.objects.filter(user=user, subscribed_to=subscribed_to).exists()