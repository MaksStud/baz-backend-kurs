import logging
import requests
import random

from django.conf import settings

from django.core.cache import cache

from .services import ValidateVisibilityServices

from celery import shared_task
from .models import Wish

logger = logging.getLogger(__name__)

validation_service = ValidateVisibilityServices()


@shared_task
def validate_video_task(wish_id):
    logger.info('Start validation video.')
    wish = Wish.objects.get(id=wish_id)
    is_valid_video = validation_service.video(file=wish.video)
    wish.is_validation = is_valid_video
    if is_valid_video is False:
        wish.video.delete()
        wish.is_validation = True
    wish.save()
    return is_valid_video


@shared_task
def validate_photo_task(wish_id):
    logger.info('Start validation photo.')
    wish = Wish.objects.get(id=wish_id)
    is_valid_photo = validation_service.photo(file=wish.photo)
    wish.is_validation = is_valid_photo
    if is_valid_photo is False:
        wish.photo.delete()
        wish.is_validation = True
    wish.save()
    return is_valid_photo


