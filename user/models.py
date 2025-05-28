from django.contrib.auth.models import (AbstractBaseUser, BaseUserManager, PermissionsMixin)
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from user import message_text

SEX_CHOICES = [
    ('M', 'Male'),
    ('F', 'Female'),
    ('O', 'Other'),
]


class BazhayUserManager(BaseUserManager):
    def create_user(self, email, password=None, username=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email field must be set'))

        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('username', email)

        return self.create_user(email, password, **extra_fields)


class BazhayUser(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model for Bazhay application.

    This model extends Django's AbstractBaseUser and PermissionsMixin to provide
    custom fields and methods for user management. It supports user registration,
    guest user functionality, and additional user attributes.
    """
    email = models.EmailField(_('email address'), unique=True, null=True)
    username = models.CharField(_('username'), max_length=150, unique=True, blank=True, null=True)
    birthday = models.DateField(blank=True, null=True)
    view_birthday = models.BooleanField(default=True, blank=True, null=True)
    sex = models.CharField(max_length=50, choices=SEX_CHOICES, blank=True, null=True)
    photo = models.ImageField(upload_to='user_photos/', blank=True, null=True)
    about_user = models.TextField(default=None, blank=True, null=True)
    is_already_registered = models.BooleanField(default=False)
    first_name = models.CharField(max_length=128, default=None, blank=True, null=True)
    last_name = models.CharField(max_length=128, default=None, blank=True, null=True)

    is_guest = models.BooleanField(default=False)
    imei = models.CharField(max_length=100, unique=True, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now, blank=True, null=True)
    is_unviewed_notification = models.BooleanField(default=False)

    objects = BazhayUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self) -> str:
        """Returns the string representation of the user, which is the email address."""
        return str(self.email)

    @property
    def fullname(self) -> str:
        return f'{self.last_name} {self.first_name}'

    def is_premium(self):
        try:
            return self.premium.is_active
        except:
            return False


class BaseAddress(models.Model):
    """ Abstract model representing a basic address with user, country, city, full name, and phone number fields.
    This model serves as a base for more specific address types."""
    user = models.ForeignKey(BazhayUser, on_delete=models.CASCADE)
    country = models.CharField(max_length=100, blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')
    full_name = models.CharField(max_length=200, blank=True, default='')
    phone_number = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        abstract = True


class Address(BaseAddress):
    """Model representing a more detailed address, extending BaseAddress to include region, street, and post index."""
    region = models.CharField(max_length=100, blank=True, default='')
    street = models.CharField(max_length=100, blank=True, default='')
    post_index = models.CharField(max_length=50, blank=True, default='')

    def __str__(self):
        return f"{self.user.username}, {self.country} {self.region} {self.city}"


class PostAddress(BaseAddress):
    """Model representing a postal address, extending BaseAddress to include post service and nearest branch."""
    post_service = models.CharField(max_length=100, blank=True, default='')
    nearest_branch = models.CharField(max_length=100, blank=True, default='')

    def __str__(self):
        return f"{self.user.username}, {self.nearest_branch}"


class BaseAccessToAddress(models.Model):
    bazhay_user = models.ForeignKey('BazhayUser', on_delete=models.CASCADE, related_name='%(class)s_given_access_to_address')
    asked_bazhay_user = models.ForeignKey('BazhayUser', on_delete=models.CASCADE, related_name='%(class)s_requested_access_to_address')
    is_approved = models.BooleanField(default=False)
    is_not_approved = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.bazhay_user} asked access to {self.asked_bazhay_user}"


class AccessToAddress(BaseAccessToAddress):
    pass


class AccessToPostAddress(BaseAccessToAddress):
    pass


class UserExponentPushToken(models.Model):
    """User Exponent Push Token model."""
    bazhay_user = models.ForeignKey(BazhayUser, on_delete=models.CASCADE, related_name='exponent_push_token')
    token = models.CharField(unique=True)
    language = models.CharField(choices=settings.LANGUAGES)
    imei = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self) -> str:
        return f'Token {self.token} owner {self.bazhay_user.email}'


@receiver(post_save, sender=AccessToPostAddress)
def send_notification_access_to_post_address(sender, instance, created, **kwargs):
    handle_access_request(
        instance=instance,
        created=created,
        message_uk_template=message_text.POST_ADDRESS_REQUEST_MESSAGE_UK,
        message_en_template=message_text.POST_ADDRESS_REQUEST_MESSAGE_EN,
        approval_url='/api/account/get-access-post-address/{instance_id}/approved/',
        approved_message_uk=message_text.POST_ADDRESS_APPROVED_MESSAGE_UK,
        approved_message_en=message_text.POST_ADDRESS_APPROVED_MESSAGE_EN,
        not_approved_message_uk=message_text.POST_ADDRESS_NOT_APPROVED_MESSAGE_UK,
        not_approved_message_en=message_text.POST_ADDRESS_NOT_APPROVED_MESSAGE_EN,
        not_approval_url='/api/account/get-access-post-address/{instance_id}/not_approved/'
    )


@receiver(post_save, sender=AccessToAddress)
def send_notification_access_to_address(sender, instance, created, **kwargs):
    handle_access_request(
        instance=instance,
        created=created,
        message_uk_template=message_text.ADDRESS_REQUEST_MESSAGE_UK,
        message_en_template=message_text.ADDRESS_REQUEST_MESSAGE_EN,
        approval_url='/api/account/get-access-address/{instance_id}/approved/',
        approved_message_uk=message_text.ADDRESS_APPROVED_MESSAGE_UK,
        approved_message_en=message_text.ADDRESS_APPROVED_MESSAGE_EN,
        not_approved_message_uk=message_text.ADDRESS_NOT_APPROVED_MESSAGE_UK,
        not_approved_message_en=message_text.ADDRESS_NOT_APPROVED_MESSAGE_EN,
        not_approval_url='/api/account/get-access-address/{instance_id}/not_approved/'
    )


def send_notification(instance, recipient, message_uk, message_en, buttons):
    from notifications.models import Notification

    notification = Notification.objects.create(
        message_uk=message_uk,
        message_en=message_en,
        button=buttons
    )
    notification.save()
    notification.users.set([recipient])


def handle_access_request(instance, created, message_uk_template, message_en_template, approval_url,
                          approved_message_uk, approved_message_en, not_approved_message_uk,
                          not_approved_message_en, not_approval_url=''):
    from ability.models import create_button
    if created:
        message_uk = message_uk_template.format(username=instance.bazhay_user.username)
        message_en = message_en_template.format(username=instance.bazhay_user.username)

        buttons = [
            create_button(
                'Yes',
                'Так',
                f'{approval_url.format(instance_id=instance.id)}',
                '',
                '',
                "That's great! Very soon you will be happier with the wish you have received.",
                "Чудово! Зовсім скоро ти станеш щасливіше від отриманого бажання.",
                '',
                '',
            ),
            create_button(
                'No',
                'Ні',
                url=not_approval_url.format(instance_id=instance.id)
            )
        ]

        send_notification(instance, instance.asked_bazhay_user, message_uk, message_en, buttons)

    if instance.is_approved:
        message_uk = approved_message_uk.format(username=instance.asked_bazhay_user.username)
        message_en = approved_message_en.format(username=instance.asked_bazhay_user.username)
        send_notification(instance, instance.bazhay_user, message_uk, message_en, [])

    if instance.is_not_approved:
        message_uk = not_approved_message_uk.format(username=instance.asked_bazhay_user.username)
        message_en = not_approved_message_en.format(username=instance.asked_bazhay_user.username)
        send_notification(instance, instance.bazhay_user, message_uk, message_en, [])