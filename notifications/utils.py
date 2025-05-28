import logging
from exponent_server_sdk import (PushClient, PushMessage, PushServerError)

from django.core.cache import cache

from user.models import UserExponentPushToken, BazhayUser
from .service import RequestsSessionSingleton


logger = logging.getLogger(__name__)


def _send_push_notifications_to_users(users: list[BazhayUser], notification, notification_data: dict = {}):
    """
    Helper function to send push notifications to users.
    :param users: Queryset or list of users
    :param notification: Notification object
    :param notification_data: Additional data (dict)
    """
    logging.info('Send Notifications')
    session = RequestsSessionSingleton.get_session()
    client = PushClient(session=session)

    for user in users:
        logging.info(f'Send to {user}')
        user_tokens = UserExponentPushToken.objects.filter(bazhay_user=user)

        for user_token in user_tokens:
            logging.info(f"{user_token}")
            if user_token.token:
                logging.info("is_unviewed_notification on True")
                cache_key = f'profile_{user.id}'
                cache.delete(cache_key)

                user.is_unviewed_notification = True
                user.save(update_fields=['is_unviewed_notification'])

                select_messages = {'uk': notification.message_uk, 'en': notification.message_en}
                body = select_messages.get(user_token.language.lower(), notification.message_uk)
                try:
                    client.publish(PushMessage(
                        to=user_token.token,
                        title=None,
                        body=body,
                        data=notification_data,
                        channel_id="default",
                        sound="default",
                    ))
                except (PushServerError, ValueError):
                    logging.error(f"{user_token} is incorrect. It is delete.")
                    user_token.delete()
                    continue


def send_push_notifications(users: list, notification):
    """
    Sending push notifications to specific users.
    """
    notification_data = {
        'message_uk': notification.message_uk,
        'message_en': notification.message_en,
        'is_button': notification.is_button,
        'button': notification.button,
    }
    _send_push_notifications_to_users(users, notification, notification_data)


def send_push_congratulatory_notification(congratulatory_notification):
    """
    Sending congratulatory push notifications to all users.
    """
    congratulatory_notification.is_send = True
    congratulatory_notification.save(update_fields=['is_send'])

    users = congratulatory_notification.users.filter(exponent_push_token__isnull=False)
    notification_data = {
        'message_uk': congratulatory_notification.message_uk,
        'message_en': congratulatory_notification.message_en,
        'is_button': False,
        'button': [],
    }
    _send_push_notifications_to_users(users, congratulatory_notification, notification_data)


def send_for_users(notification):
    users = notification.users.filter(exponent_push_token__isnull=False).distinct()
    logger.info(f'Send notification to users: {users}')
    send_push_notifications(users, notification)
