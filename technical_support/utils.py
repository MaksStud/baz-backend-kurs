import logging
import os
import mimetypes

import base64
from django.core.files.uploadedfile import InMemoryUploadedFile
from io import BytesIO

from asgiref.sync import sync_to_async
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .serializers import TechnicalSupportChatMessageSerializer

from .models import TechnicalSupportEmail, TechnicalSupportChatMessage, TechnicalSupportChat

logger = logging.getLogger(__name__)


def get_admin_email() -> str:
    """Returns the primary administrator address or the backup address."""
    email_model = TechnicalSupportEmail.objects.first()
    if email_model and email_model.admin_email:
        return email_model.admin_email

    admin_email = os.getenv('TECHNICAL_SUPPORT_ADMIN')
    if admin_email:
        return admin_email

    logger.warning("Main admin email not found.")


def create_answer_to_user(chat: TechnicalSupportChat, text: str) -> None:
    """Create answer to user."""
    message = TechnicalSupportChatMessage.objects.create(
        chat=chat,
        message_text=text,
    )
    send_message_via_websocket(chat.id, message)


def send_message_via_websocket(chat_id: int, message_instance: TechnicalSupportChatMessage):
    """
    Sends a message to a WebSocket chat group.

    :param chat_id: The ID of the chat where the message will be sent.
    :param message_instance: The message instance (TechnicalSupportChatMessage).
    """
    channel_layer = get_channel_layer()
    group_name = f"chat_{chat_id}"

    serializer = TechnicalSupportChatMessageSerializer(message_instance)
    message_data = serializer.data

    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "chat_message",
            "message": message_data,
        },
    )


@sync_to_async
def decode_base64_file(file_data: str, file_name: str = None):
    """
    Decode base64 file data and return an InMemoryUploadedFile.

    :param file_data: The base64-encoded file data (optionally prefixed with metadata).
    :param file_name: The name to be given to the file (optional).
    :return: An InMemoryUploadedFile instance or None if decoding fails.
    """
    try:
        if ',' in file_data:
            metadata, file_data = file_data.split(',', 1)
            mime_type = metadata.split(';')[0].split(':')[1]
        else:
            mime_type = 'application/octet-stream'

        file_content = base64.b64decode(file_data)
        logger.info(f"Decoded file content of length {len(file_content)}")

        extension = mimetypes.guess_extension(mime_type) or ''

        if not file_name:
            file_name = f"uploaded_file{extension}"

        # Create an InMemoryUploadedFile instance
        file = InMemoryUploadedFile(
            BytesIO(file_content),
            field_name=None,
            name=file_name,
            content_type=mime_type,
            size=len(file_content),
            charset=None
        )
        logger.info(f"File successfully decoded: {file.name}, size: {file.size}")
        return file

    except Exception as error:
        logger.error(f"Error decoding file: {error}")
        return None

