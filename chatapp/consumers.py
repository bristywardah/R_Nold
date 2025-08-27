import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.core.cache import cache  
from .models import Message

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        self.room_group_name = f"user_{self.user.id}"

        cache.set(f"user_active_{self.user.id}", True, timeout=None)

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        cache.set(f"user_active_{self.user.id}", False, timeout=None)

        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        receiver_id = data.get("user_id")
        message = data.get("message")

        if not receiver_id or not message:
            return

        msg = await self.save_message(self.user.id, receiver_id, message)

        receiver_online = cache.get(f"user_active_{receiver_id}", False)

        await self.send(text_data=json.dumps({
            "status": "sent",
            "message_id": msg.id,
            "sender": self.user.id,
            "receiver": receiver_id,
            "message": msg.message,
            "timestamp": str(msg.timestamp),
            "receiver_online": receiver_online  
        }))

        if receiver_online:
            await self.channel_layer.group_send(
                f"user_{receiver_id}",
                {
                    "type": "chat_message",
                    "message_id": msg.id,
                    "sender": self.user.id,
                    "receiver": receiver_id,
                    "message": msg.message,
                    "timestamp": str(msg.timestamp),
                }
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "status": "received",
            **event
        }))

    @database_sync_to_async
    def save_message(self, sender_id, receiver_id, message):
        sender = User.objects.get(id=sender_id)
        receiver = User.objects.get(id=receiver_id)
        return Message.objects.create(sender=sender, receiver=receiver, message=message)
