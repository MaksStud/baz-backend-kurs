from django.db import models
from rest_framework.serializers import ValidationError

from user.models import BazhayUser

ALLOWED_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'mp4', 'mov', 'avi']


def validate_image_or_video(value):
    """
    Validate image or video.
    If file valid return None, else raise ValidationError.

    :param value: File.
    """
    extension = value.name.split('.')[-1].lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError(detail=f'Allowed types are: {", ".join(ALLOWED_EXTENSIONS)}')


class TechnicalSupportChat(models.Model):
    """Technical support chat model."""
    title = models.CharField(max_length=300, blank=True, null=True)
    bazhay_user = models.OneToOneField(BazhayUser, on_delete=models.CASCADE, related_name='technical_support_chat')
    last_action_time = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return f'Chat {self.bazhay_user}'


class TechnicalSupportChatMessage(models.Model):
    """Technical support chat message model."""
    chat = models.ForeignKey(TechnicalSupportChat, on_delete=models.CASCADE, related_name='chat_message')
    message_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    file = models.FileField(upload_to='technical_support_files/', validators=[validate_image_or_video], blank=True, null=True)
    from_user = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.chat}: message {self.message_text}'


class TechnicalSupportEmail(models.Model):
    """Admin email."""
    admin_email = models.EmailField(
        verbose_name="Administrator address for technical support",
        help_text="Email address to which support requests will be sent."
    )

    def __str__(self) -> str:
        return self.admin_email
