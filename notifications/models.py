import logging

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

from .tasks import send_notification_task

logger = logging.getLogger(__name__)

User = get_user_model()


class AbstractNotification(models.Model):
    message = models.TextField()
    send_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Notification: {self.message[:20]} at {self.send_at}'

    class Meta:
        abstract = True


class Notification(AbstractNotification):
    """
    Model representing a notification.
    """
    users = models.ManyToManyField(User, related_name='notifications', blank=True)
    button = models.JSONField(default=list, blank=True, null=True)
    is_button = models.BooleanField(default=False)
    is_send_back = models.BooleanField(default=True)

    def is_send(self) -> bool:
        """
        Checks if the notification has been sent based on the current time.
        """
        return self.send_at <= timezone.now()


class CongratulatoryNotification(AbstractNotification):
    """
    Model representing a congratulatory notification.
    """
    is_send = models.BooleanField(default=False)
    users = models.ManyToManyField(User, related_name='congratulatory_notifications', blank=True)


@receiver(post_save, sender=Notification)
def schedule_notification(sender, instance, created, **kwargs):
    """
    Schedule a notification to be sent at the specified time.

    When a new notification is created, it calculates the delay until
    it should be sent and schedules a task to send it.

    :param sender: The model class (Notification).
    :param instance: The actual Notification instance.
    :param created: Boolean indicating if the Notification was created.
    """
    if created and instance.is_send_back:
        delay = (instance.send_at - timezone.now()).total_seconds()
        if delay <= 0:
            delay = 1
        send_notification_task.apply_async((instance.id,), countdown=delay)
        logger.info('Send Notifications')


