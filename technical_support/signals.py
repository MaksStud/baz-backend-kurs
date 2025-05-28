import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import TechnicalSupportChatMessage
from .tasks import send_to_user, send_to_admin


@receiver(post_save, sender=TechnicalSupportChatMessage)
def send_message(sender, instance: TechnicalSupportChatMessage, created: bool, **kwargs):
    """Send to user or admin depending on the type of message."""
    if created:
        match instance.from_user:
            case False:
                send_to_user.delay(instance.message_text, instance.chat.bazhay_user.id)
            case True:
                send_to_admin.delay(instance.chat.title, instance.message_text)

