import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .utils import send_for_users, send_push_congratulatory_notification

logger = logging.getLogger(__name__)


@shared_task
def send_notification_task(notification_id: int) -> None:
    """
    Send a notification to users at the scheduled time or to a general group
    if no users are specified.

    :param notification_id: The ID of the notification to send.
    """
    from .models import Notification
    try:
        notification = Notification.objects.get(id=notification_id)

        if not notification:
            logger.warning(f"Notification ID {notification_id} has been deleted. Skipping.")
            return

        if notification.send_at <= timezone.now() and notification.users.exists():
            send_for_users(notification)

    except Exception as e:
        logger.error(f"Failed to send notification ID {notification_id}: {e}", exc_info=True)


@shared_task
def send_congratulatory_notification() -> None:
    """
    Send a congratulatory notification to all users.
    """
    from .models import CongratulatoryNotification

    start_time = timezone.now().replace(second=0, microsecond=0)
    end_time = start_time + timedelta(minutes=1)

    congratulatory_notifications = CongratulatoryNotification.objects.filter(
        is_send=False,
        send_at__gte=start_time,
        send_at__lt=end_time
    )

    for congratulatory_notification in congratulatory_notifications:
        send_push_congratulatory_notification(congratulatory_notification)
