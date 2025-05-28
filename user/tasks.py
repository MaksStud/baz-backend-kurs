import logging
import os
from datetime import timedelta

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

from .models import send_notification, BazhayUser
from user import message_text

from .message_text import CONFIRM_CODE

logger = logging.getLogger(__name__)


@shared_task
def send_email_confirm_code(email: str, confirmation_code: str, otp_time_life: int) -> None:
    """
    Celery task to send a confirmation email with a provided code.
    This task sends an email containing the confirmation code to the specified email address.
    It uses Django's email backend to send the email.

    :param email: The recipient's email address.
    :param confirmation_code: The confirmation code to include in the email.
    :param otp_time_life: lifetime of a single-use password in minet.
    """
    logger.info(f"Send to EMAIL: {email}, confirm code: {confirmation_code}")

    return send_mail(
        'Твій одноразовий пароль',
        CONFIRM_CODE.format(confirmation_code=confirmation_code, otp_time_life=otp_time_life),
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False,
    )


@shared_task
def send_email(email: str, title: str, text: str) -> None | int:
    """
    Celery task to send email.

    :param email: Recipient email.
    :param title: Title in mail.
    :param text: Text in mail.

    :return: Status code.
    """
    try:
        logging.info("Send to EMAIL: %s, text: %d", email, text)
        return send_mail(title, text, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
    except Exception as e:
        logging.error(f"Error sending email: {str(e)}")
        raise


@shared_task
def check_birthdays_and_notify():
    """
    A task to check which users have a birthday in 15 days and send notifications.
    It also checks if it is a birthday.
    """
    today = timezone.now().date()
    target_date = today + timedelta(days=15)

    users_with_upcoming_birthdays = BazhayUser.objects.filter(
        birthday__month=target_date.month,
        birthday__day=target_date.day,
    )
    logger.info(f"Birthday in 15 days in {users_with_upcoming_birthdays}")

    users_with_today_birthday = BazhayUser.objects.filter(
        birthday__month=today.month,
        birthday__day=today.day,
    )

    logger.info(f"Birthday today in {users_with_today_birthday}")

    for user in users_with_upcoming_birthdays:

        send_birthday_notifications(
            user,
            message_text.REMINDER_OF_BIRTHDAY_TO_BIRTHDAY_BOY_UK,
            message_text.REMINDER_OF_BIRTHDAY_TO_BIRTHDAY_BOY_EN,
            message_text.REMINDER_OF_BIRTHDAY_FOR_BIRTHDAY_BOY_SUBSCRIBERS_UK.format(username=user.username),
            message_text.REMINDER_OF_BIRTHDAY_FOR_BIRTHDAY_BOY_SUBSCRIBERS_EN.format(username=user.username),
        )

    for user in users_with_today_birthday:
        send_birthday_notifications(
            user,
            message_text.BIRTHDAY_TO_BIRTHDAY_BOY_UK,
            message_text.BIRTHDAY_TO_BIRTHDAY_BOY_EN,
            message_text.BIRTHDAY_FOR_BIRTHDAY_BOY_SUBSCRIBERS_UK.format(username=user.username),
            message_text.BIRTHDAY_FOR_BIRTHDAY_BOY_SUBSCRIBERS_EN.format(username=user.username),
        )


def send_birthday_notifications(user, birthday_boy_message_uk, birthday_boy_message_en, birthday_boy_sub_message_uk,
                                birthday_boy_sub_message_en):
    """
    An auxiliary function for sending notifications to users and their subscribers.
    :param user: a user who has a birthday.
    :param birthday_boy_message_uk: Sending a birthday message to owner in Ukrainian.
    :param birthday_boy_message_en: Sending a birthday message to owner in English.
    :param birthday_boy_sub_message_uk: Sending a birthday message to subscribers in Ukrainian.
    :param birthday_boy_sub_message_en: Sending a birthday message to subscribers in English.
    """

    logging.info(f"Birthday message to {user.email}")
    send_notification(
        instance=user,
        recipient=user,
        message_uk=birthday_boy_message_uk,
        message_en=birthday_boy_message_en,
        buttons=[]
    )

    for subscription in user.subscribers.all():
        logging.info(f"Birthday message to {subscription.user.email}")
        send_notification(
            instance=user,
            recipient=subscription.user,
            message_uk=birthday_boy_sub_message_uk,
            message_en=birthday_boy_sub_message_en,
            buttons=[]
        )

@shared_task
def delete_guest_user():
    two_days_ago = timezone.now() - timedelta(days=int(os.getenv('DELETE_GUEST_USERS_DAYS', 2)))
    users = BazhayUser.objects.filter(is_guest=True, date_joined__lte=two_days_ago)
    logger.info(f'User list {users}')

    for user in users:
        logger.info(f'Delete user {user}')
        user.delete()

