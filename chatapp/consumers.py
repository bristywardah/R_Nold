import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from .models import Message, Chat
from notification.utils import create_chat_notification  # তোমার utils এ থাকবে

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close()
            return

        # Own group name (একজন ইউজার নিজের group এ থাকবে)
        self.room_group_name = f"chat_{self.user.id}"

        # Cache + DB তে online status update
        cache.set(f"user_active_{self.user.id}", True, timeout=None)
        await self.set_user_online(self.user.id, True)

        # Group এ join
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        cache.set(f"user_active_{self.user.id}", False, timeout=None)
        await self.set_user_online(self.user.id, False)
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        """
        Expecting JSON:
        {
            "user_id": <receiver_id>,
            "message": "Hello",
            "reply_to": <optional_message_id>
        }
        """
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"error": "Invalid JSON"}))
            return

        receiver_id = data.get("user_id")
        message = data.get("message")
        reply_to_id = data.get("reply_to")

        if not receiver_id or not message:
            await self.send(text_data=json.dumps({"error": "user_id and message required"}))
            return

        # Save message in DB
        msg = await self.save_message(self.user.id, receiver_id, message, reply_to_id)

        # Confirm to sender
        await self.send(text_data=json.dumps({
            "status": "sent",
            "message_id": msg.id,
            "sender": self.user.id,
            "receiver": receiver_id,
            "message": msg.message,
            "timestamp": str(msg.timestamp),
        }))

        # Send to receiver if online
        receiver_online = cache.get(f"user_active_{receiver_id}", False)
        if receiver_online:
            await self.channel_layer.group_send(
                f"chat_{receiver_id}",
                {
                    "type": "chat_message",
                    "message_id": msg.id,
                    "sender": self.user.id,
                    "receiver": receiver_id,
                    "message": msg.message,
                    "timestamp": str(msg.timestamp),
                }
            )

        # Always create notification for receiver
        receiver = await self.get_user(receiver_id)
        await create_chat_notification(receiver, msg)

    async def chat_message(self, event):
        """Receive message from group -> send to WebSocket"""
        await self.send(text_data=json.dumps({
            "status": "received",
            **event
        }))

    # ---------------- DB / Helper methods ---------------- #

    @database_sync_to_async
    def save_message(self, sender_id, receiver_id, message, reply_to_id=None):
        sender = User.objects.get(id=sender_id)
        receiver = User.objects.get(id=receiver_id)
        reply_to = Message.objects.filter(id=reply_to_id).first() if reply_to_id else None

        msg = Message.objects.create(
            sender=sender,
            receiver=receiver,
            message=message,
            reply_to=reply_to,
            timestamp=timezone.now(),
        )

        # Ensure Chat exists both directions
        Chat.objects.get_or_create(sender=sender, receiver=receiver)
        Chat.objects.get_or_create(sender=receiver, receiver=sender)

        return msg

    @database_sync_to_async
    def set_user_online(self, user_id, status: bool):
        User.objects.filter(id=user_id).update(is_online=status)

    @database_sync_to_async
    def get_user(self, user_id):
        return User.objects.get(id=user_id)
