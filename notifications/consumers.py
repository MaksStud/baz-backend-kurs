import json

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from .models import Notification


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get('user')

        if self.user is None:
            await self.close(code=4001)
            return

        self.notifications_group = 'notifications_group'
        self.personal_group = f"user_{self.user.id}"

        await self.channel_layer.group_add(
            self.notifications_group,
            self.channel_name
        )

        await self.channel_layer.group_add(
            self.personal_group,
            self.channel_name
        )

        await self.accept()

        if not self.user.is_already_registered:
            message = await database_sync_to_async(
                lambda: Notification.objects.filter(message_en='Hi there! We’re happy to welcome you to Bazhay!').first()
            )()

            if message:
                await self.channel_layer.group_send(
                    self.personal_group,
                    {
                        'type': 'send_notification',
                        'message': {
                            'message_en': message.message_en,
                            'message_uk': message.message_uk,
                        }
                    }
                )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.notifications_group,
            self.channel_name
        )
        await self.channel_layer.group_discard(
            self.personal_group,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get('message')

        notification = await database_sync_to_async(Notification.objects.create)(
            message_en=message.get('message_en'),
            message_uk=message.get('message_uk'),
            is_button=message.get('is_button'),
            button=message.get('button')
        )

        await database_sync_to_async(notification.users.add)(self.user)

    async def send_notification(self, event):
        message = event['message']
        await self.send(text_data=json.dumps({
            'message': message
        }))

