import logging

from celery import shared_task
from health_check.plugins import plugin_dir
from .utils import send_telegram_alert

logger = logging.getLogger(__name__)


@shared_task
def scheduled_health_check():
    """Health check if error send telegram message."""
    errors = []
    for plugin_class, _ in plugin_dir._registry:
        if plugin_class.__name__ == "CeleryHealthCheckCelery":
            continue

        check = plugin_class()
        check.run_check()

        if check.errors:
            errors.append(f"{plugin_class.__name__}: {check.errors}")

    if errors:
        send_telegram_alert(f"⚠️ Health check failed: {errors}")
    else:
        logger.info("✅ Health check passed")