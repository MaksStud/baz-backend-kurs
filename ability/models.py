import logging

from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

import ability.choices as choices

from user.models import BazhayUser
from brand.models import Brand
from news.models import News
from notifications.models import Notification

from django.db.models.signals import post_save
from django.dispatch import receiver

from ability import notifications_texts

logger = logging.getLogger(__name__)


def validate_video_file(file) -> None:
    """
    Validates that the uploaded file is a video file based on its extension.
    """
    if file is None:
        return

    file_extension = file.name.split('.')[-1].lower()

    if f".{file_extension}" not in choices.valid_mime_types:
        raise ValidationError('Only video files are allowed.')


class Wish(models.Model):
    """
    Model representing a wish or request for a specific item or experience.

    """
    ACCESS_TYPE_CHOICES = choices.access_type_choices
    CURRENCY_CHOICES = choices.currency_choices
    IMAGE_SIZE_CHOICES = choices.image_size_choices

    name = models.CharField(max_length=128)
    photo = models.ImageField(upload_to='ability_media/',  blank=True, null=True,)
    video = models.FileField(upload_to='ability_media/', blank=True, null=True, validators=[validate_video_file])
    image_size = models.FloatField(blank=True, null=True)
    price = models.FloatField(blank=True, null=True)
    link = models.TextField(blank=True, null=True, validators=[URLValidator()])
    description = models.TextField(blank=True, null=True)
    additional_description = models.TextField(blank=True, null=True)
    access_type = models.CharField(max_length=20, choices=ACCESS_TYPE_CHOICES, default='everyone')
    author = models.ForeignKey(BazhayUser, related_name='abilities', on_delete=models.CASCADE, blank=True, null=True)
    brand_author = models.ForeignKey(Brand, related_name='wishes', on_delete=models.CASCADE, blank=True, null=True)
    news_author = models.ForeignKey(News, related_name='wishes', on_delete=models.CASCADE, blank=True, null=True)
    currency = models.CharField(max_length=50, null=True, blank=True,  choices=CURRENCY_CHOICES)
    is_fully_created = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    views_number = models.PositiveIntegerField(blank=True, null=True, default=0)
    is_fulfilled = models.BooleanField(default=False)
    is_validation = models.BooleanField(default=True)
    is_copied_from_brand = models.BooleanField(default=False)
    image_size_choice = models.CharField(max_length=50, null=True, blank=True,  choices=IMAGE_SIZE_CHOICES)

    def __str__(self) -> str:
        """Return the name of the wish."""
        return str(self.name)

    def display_author(self) -> str:
        """
        Returns a string representation of the author of the wish.

        If the wish has an author, the author's email is returned. If a brand author is present,
        the brand's name is returned. If neither is available, a dash ('-') is returned.

        :returns (str): The email of the author, the brand name, or a dash ('-').
        """
        if self.author:
            return self.author.email
        elif self.brand_author:
            return self.brand_author.name
        return '-'

    display_author.short_description = 'Author'

    def save(self, *args, **kwargs):
        if self.image_size_choice:
            self.image_size = float(self.image_size_choice)
        super().save(*args, **kwargs)
      

class Reservation(models.Model):
    """
    Reservation of a wish for a users.
    """
    wish = models.ForeignKey(Wish, on_delete=models.CASCADE, related_name='reservation')
    selected_user = models.ForeignKey(BazhayUser, on_delete=models.CASCADE, related_name='reservation', null=True, blank=True)

    def is_active(self):
        return False if self.selected_user else True

    def __str__(self):
        return f"wish {self.wish.name} reservation to {self.selected_user}"


class CandidatesForReservation(models.Model):
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name='candidates')
    bazhay_user = models.ForeignKey(BazhayUser, on_delete=models.CASCADE, related_name='candidates')

    def __str__(self):
         return f"reservation {self.reservation.wish.name} candidates {self.bazhay_user}"


class AccessToViewWish(models.Model):
    wish = models.OneToOneField(Wish, on_delete=models.CASCADE, related_name='access_to_view_wish',
                                null=True, blank=True)


class AccessToViewWishUser(models.Model):
    user = models.ForeignKey(BazhayUser, on_delete=models.CASCADE, related_name='access_to_view_wish_users')
    access_to_view_wish = models.ForeignKey(AccessToViewWish, on_delete=models.CASCADE, related_name='access_users')


@receiver(post_save, sender=Reservation)
def send_notification_on_user_select(sender, instance, **kwargs):
    if instance.selected_user:
        if not instance.wish.author.is_premium():
            logger.info('Send notification to author.')
            message_uk = notifications_texts.NON_PREMIUM_AUTHOR_MESSAGE_UK.format(wish_name=instance.wish.name)
            message_en = notifications_texts.NON_PREMIUM_AUTHOR_MESSAGE_EN.format(wish_name=instance.wish.name)
            button = [
                create_button(
                    notifications_texts.BUTTON_TEXT_EN,
                    notifications_texts.BUTTON_TEXT_UK,
                    f'/api/wish/reservation/?wish={instance.wish.id}',
                    ok_text_en=notifications_texts.OK_TEXT_EN.format(username=instance.selected_user.username),
                    ok_text_uk=notifications_texts.OK_TEXT_UK.format(username=instance.selected_user.username),
                    not_ok_text_en=notifications_texts.NOT_OK_TEXT_EN,
                    not_ok_text_uk=notifications_texts.NOT_OK_TEXT_UK,
                )
            ]

            notification = Notification.objects.create(
                message_uk=message_uk,
                message_en=message_en,
                button=button
            )
            notification.users.set([instance.wish.author])
            notification.save()

        message_uk = notifications_texts.SELECTED_USER_MESSAGE_UK.format(
            wish_name=instance.wish.name,
            author_username=instance.wish.author.username
        )
        message_en = notifications_texts.SELECTED_USER_MESSAGE_EN.format(
            wish_name=instance.wish.name,
            author_username=instance.wish.author.username
        )

        logger.info('Send notification to selected user.')
        notification_to_selected_user = Notification.objects.create(
            message_uk=message_uk,
            message_en=message_en,
            button=[]
        )
        notification_to_selected_user.users.set([instance.selected_user])
        notification_to_selected_user.save()

        other_candidates = CandidatesForReservation.objects.filter(reservation=instance).exclude(
            bazhay_user=instance.selected_user
        )

        message_uk = notifications_texts.OTHER_CANDIDATES_MESSAGE_UK.format(
            author_username=instance.wish.author.username,
            wish_name=instance.wish.name
        )
        message_en = notifications_texts.OTHER_CANDIDATES_MESSAGE_EN.format(
            author_username=instance.wish.author.username,
            wish_name=instance.wish.name
        )
        button = []

        for candidate in other_candidates:
            notification_to_other_user = Notification.objects.create(
                message_uk=message_uk,
                message_en=message_en,
                button=button
            )
            notification_to_other_user.users.set([candidate.bazhay_user])
            notification_to_other_user.save()


@receiver(post_save, sender=CandidatesForReservation)
def send_notification_on_if_new_candidate(sender, instance, created, **kwargs):
    if created:
        logger.info(f'Send notification about new  candidate {instance.bazhay_user}')
        message_uk = notifications_texts.RESERVATION_REQUEST_MESSAGE_UK.format(
            wish_name=instance.reservation.wish.name,
            username=instance.bazhay_user.username,
        )
        message_en = notifications_texts.RESERVATION_REQUEST_MESSAGE_EN.format(
            wish_name=instance.reservation.wish.name,
            username=instance.bazhay_user.username,
        )
        button = [
            create_button(
                "Yes",
                "Так",
                f"/api/wish/reservation/{instance.reservation.id}/select_user/",
                "candidate_id",
                f"{instance.bazhay_user.id}",
                notifications_texts.BUTTON_YES_TEXT_EN,
                notifications_texts.BUTTON_YES_TEXT_UK,
                notifications_texts.BUTTON_NO_TEXT_EN,
                notifications_texts.BUTTON_NO_TEXT_UK,
            ),
            create_button(
                "No",
                "Ні",
                not_ok_text_en=notifications_texts.BUTTON_NO_TEXT_EN,
                not_ok_text_uk=notifications_texts.BUTTON_NO_TEXT_UK,
                ok_text_en=notifications_texts.BUTTON_NO_TEXT_EN,
                ok_text_uk=notifications_texts.BUTTON_NO_TEXT_UK,
            ),
        ]

        notification = Notification.objects.create(
            message_uk=message_uk,
            message_en=message_en,
            button=button,
        )
        notification.users.set([instance.reservation.wish.author])
        notification.save()


def create_button(text_en: str = '', text_uk: str = '', url: str = '', name_param: str = '', value_param: str = '', ok_text_en: str = '',
                  ok_text_uk: str = '', not_ok_text_en: str = '', not_ok_text_uk: str = ''):
    return {'text_en': text_en,
            'text_uk': text_uk,
            'request': {'url': url,
                        'body': {name_param: value_param,}},
            'response_ok_text': {'ok_text_en': ok_text_en,
                                 'ok_text_uk': ok_text_uk},
            'response_not_ok_text': {'not_ok_text_en': not_ok_text_en,
                                     'not_ok_text_uk': not_ok_text_uk}
            }


def create_message(button: list, text_en: str = "", text_uk: str = "",):
    return {'message_en': text_en,
            'message_uk': text_uk,
            'button': button}
