import os
import json
import logging

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

from .constants import technical_support_message
from .models import TechnicalSupportChat
from .serializers import TechnicalSupportChatMessageSerializer
from .utils import decode_base64_file, create_answer_to_user
from user.models import BazhayUser

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self) -> None:
        """
        Connect to web socket.

        This method is called when a WebSocket connection is initiated.
        It verifies user access to the chat and adds the connection to the appropriate group.

        :return: None
        """
        self.chat_id = self.scope['url_route']['kwargs']['chat_id']
        self.room_group_name = f"chat_{self.chat_id}"
        logger.info(f"New connection to chat with id {self.chat_id}")
        user = self.scope['user']

        logger.info(f'User from scope {user}')

        if not await self.check_chat_access(user, await self.chat()):
            logger.warning(f"Access denied for user {self.scope['user']} to chat {self.chat_id}")
            await self.close()
            return

        logger.info('Add to groups.')
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code: int) -> None:
        """
        Disconnect from web socket.

        This method is called when a WebSocket connection is closed.
        It removes the connection from the appropriate group.

        :param close_code: WebSocket close code.
        :return: None
        """
        logger.info('Disconnect from groups.')
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data: str) -> None:
        """
        Receive a message from WebSocket.

        This method processes incoming WebSocket messages, validates them,
        and sends responses to the group.

        :param text_data: JSON string containing the message data.
        :return: None
        """
        data = json.loads(text_data)

        file_data = data.get('file')
        if file_data:
            file = await decode_base64_file(file_data.get('content', ''), file_data.get('name', 'uploaded_file.png'))
            logger.info(f"Decoded file: {file}")
            data['file'] = file

        serializer = TechnicalSupportChatMessageSerializer(data=data)
        if serializer.is_valid():
            logger.info('Message is valid. Saving message.')
            await self.is_first_message(await self.chat(), data.get('message_text'), data.get('from_user'))
            message = await sync_to_async(serializer.save)(chat_id=self.chat_id)

            message = TechnicalSupportChatMessageSerializer(message).data

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message
                }
            )

            await self.send_answer_to_user(await self.chat(), technical_support_message, data.get('from_user'))
            await self.set_chat_in_active_status(await self.chat())
        else:
            await self.send(text_data=json.dumps({'errors': serializer.errors}))

    async def chat_message(self, event: dict) -> None:
        """
        Send a chat message to WebSocket.

        This method sends a chat message to the WebSocket client.

        :param event: Dictionary containing the message data.
        :return: None
        """
        message = event['message']
        await self.send(text_data=json.dumps(message))

    async def check_chat_access(self, user: BazhayUser, chat: TechnicalSupportChat) -> bool:
        """
        Checks if the user has access to the chat.

        This method verifies if the user is allowed to access the specified chat.

        :param user: The user object from the WebSocket scope.
        :param chat: Chat to access.
        :return: Boolean indicating access permission.
        """
        try:
            if await sync_to_async(lambda: user.is_superuser)():
                return True

            elif await sync_to_async(lambda: chat.bazhay_user == user)():
                return True
            return False

        except TechnicalSupportChat.DoesNotExist:
            return False

    async def is_first_message(self, chat: TechnicalSupportChat, message_text: str, from_user: bool) -> None:
        """
        Handle the first message in a chat.

        Updates the chat title if it's the first message and the chat is inactive.

        :param chat: Chat.
        :param message_text: Text of the message.
        :param from_user: Boolean indicating if the message is from a user.
        :return: None
        """
        if not chat.is_active and from_user:
            chat.title = message_text
            await sync_to_async(chat.save)(update_fields=['title'])

    async def send_answer_to_user(self, chat: TechnicalSupportChat, text: str, from_user: bool) -> None:
        """
        Send an answer to the user asynchronously.

        Sends a predefined answer to the user if the chat is inactive.

        :param chat: Chat.
        :param text: Text of the answer to send.
        :param from_user: Boolean indicating if the message is from a user.

        :return: None
        """
        if not chat.is_active and from_user:
            await sync_to_async(create_answer_to_user)(chat, text)

    async def set_chat_in_active_status(self, chat: TechnicalSupportChat) -> None:
        """
        Set the chat to active status.

        Updates the chat's last action time and marks it as active.

        :param chat: Chat.
        :return: None
        """
        chat.last_action_time = timezone.now()
        chat.is_active = True
        await sync_to_async(chat.save)(update_fields=['last_action_time', 'is_active'])

    async def chat(self) -> TechnicalSupportChat:
        """
        Return chat.

        :return: Return TechnicalSupportChat obj.
        """
        return await sync_to_async(TechnicalSupportChat.objects.get)(id=self.chat_id)
