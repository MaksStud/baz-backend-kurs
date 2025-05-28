import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils.timezone import now

from exponent_server_sdk import PushClient, PushMessage, PushServerError

from .models import TechnicalSupportChat
from .utils import get_admin_email

from notifications.service import RequestsSessionSingleton
from user.models import UserExponentPushToken, BazhayUser

logger = logging.getLogger(__name__)


@shared_task
def deactivate_inactive_chats():
    """Deactivates the chat after a certain amount of inactivity."""
    minutes_ago = now() - timedelta(minutes=settings.TIME_LIFE_CHAT)
    chats_to_deactivate = TechnicalSupportChat.objects.filter(is_active=True, last_action_time__lt=minutes_ago)
    logger.info(f'Chats to deactivate: {chats_to_deactivate}')
    chats_to_deactivate.update(is_active=False)


@shared_task
def send_to_admin(title: str, message: str) -> int:
    """
    Send email to admin.

    :param title: Email letter title.
    :param message: Email letter text.

    :return: Status (type integer).
    """

    return send_mail(
        title,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [get_admin_email()],
        fail_silently=False,
    )


@shared_task
def send_to_user(message: str, user_id: int) -> None:
    """
    Send to user via push message.

    :param message: Message text.
    :param user_id: ID user.

    :return: None
    """
    session = RequestsSessionSingleton.get_session()
    client = PushClient(session=session)
    user = BazhayUser.objects.get(id=user_id)
    user_tokens = UserExponentPushToken.objects.filter(bazhay_user=user)
    logger.info(f'Send to {user}')

    choice_title = {'en': 'Technical support', 'uk': 'Технічна підтримка'}

    for user_token in user_tokens:
        logging.info(f"{user_token}")
        if user_token.token:
            try:
                client.publish(PushMessage(
                    to=user_token.token,
                    title=choice_title.get(user_token.language, 'Технічна підтримка'),
                    body=message,
                    data={},
                    channel_id="tech_support",
                    sound="default",
                ))
            except (PushServerError, ValueError):
                logging.error(f"{user_token} is incorrect. It is delete.")
                user_token.delete()
                continue

