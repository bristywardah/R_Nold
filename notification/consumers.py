import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from users.models import User
from users.enums import UserRole
from .models import Notification
from .serializers import NotificationSerializer


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        """
        Accept connection only for authenticated users
        and add them to their respective notification group.
        """
        await self.accept()
        user = self.scope.get("user")

        if not isinstance(user, User) or not user.is_authenticated:
            await self.send_json({"error": "Unauthorized"})
            await self.close()
            return

        self.user = user
        self.room_group_name = self.get_group_name(user)

        print(f"✅ Connecting {user.email} to group {self.room_group_name}")

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

    async def disconnect(self, close_code):
        """Remove user from group on disconnect."""
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive_json(self, content, **kwargs):
        """
        Handle incoming WebSocket messages.
        Expected format:
        {
            "type": "send_notification",
            "notification": { ... }
        }
        """
        message_type = content.get("type")
        if message_type == "send_notification":
            notification_data = content.get("notification")
            if not notification_data:
                await self.send_json({"error": "No notification data provided"})
                return

            # Save notification & serialize
            notification_data = await self.save_and_serialize_notification(notification_data)

            # Broadcast to the group
            group_name = self.get_group_name(self.user)
            await self.channel_layer.group_send(
                group_name,
                {
                    "type": "send_notification",
                    "notification": notification_data,
                }
            )

    async def send_notification(self, event):
        print(" Sending notification via WebSocket:", event)

        """
        Send serialized notification data to WebSocket client.
        """
        notification_data = event.get("notification", {})

        # Build display name with role label
        name = f"{self.user.first_name} {self.user.last_name}".strip() or self.user.email
        role_label = getattr(self.user, "role", "").lower()

        if role_label == UserRole.VENDOR.value:
            notification_data["full_name"] = f"Vendor: {name}"
        elif role_label == UserRole.CUSTOMER.value:
            notification_data["full_name"] = f"Customer: {name}"
        elif role_label == UserRole.ADMIN.value or self.user.is_staff:
            notification_data["full_name"] = f"Admin: {name}"
        else:
            notification_data["full_name"] = name

        await self.send_json({
            "type": "notification",
            "data": notification_data,
        })

    def get_group_name(self, user: User) -> str:
        """
        Return WebSocket group name based on user role:
        - Admin/Staff: "notifications_admins"
        - Vendor: "notifications_vendor_<id>"
        - Customer: "notifications_user_<id>"
        """
        role = getattr(user, "role", "").lower()
        if role == UserRole.ADMIN.value or user.is_staff:
            return "notifications_admins"
        elif role == UserRole.VENDOR.value:
            return f"notifications_vendor_{user.id}"
        return f"notifications_user_{user.id}"

    def prepare_meta_data(self, message: str, base_meta_data=None) -> dict:
        """
        Parse meta_data based on message keywords.
        """
        meta_data = base_meta_data or {}
        message_upper = (message or "").upper()

        if "MESSAGE" in message_upper or "CHAT" in message_upper:
            meta_data["type"] = "chat"
            meta_data["chat_type"] = "direct"
        elif "ORDER" in message_upper:
            meta_data["type"] = "order"
            if base_meta_data:
                meta_data["order_id"] = base_meta_data.get("order_id")
                meta_data["order_status"] = base_meta_data.get("order_status")
                meta_data["project_id"] = base_meta_data.get("project_id")
        elif "PAYMENT" in message_upper:
            meta_data["type"] = "payment"
            if base_meta_data:
                meta_data["payment_id"] = base_meta_data.get("payment_id")

        return meta_data

    @database_sync_to_async
    def save_and_serialize_notification(self, data: dict) -> dict:
        """
        Save a new notification to DB and serialize it.
        """
        message = data.get("message", "")
        meta_data = self.prepare_meta_data(message, data.get("meta_data", {}))

        notification = Notification.objects.create(
            user=self.user,
            message=message,
            seen=data.get("seen", False),
            meta_data=meta_data,
        )

        notification = Notification.objects.select_related("user", "sender").get(id=notification.id)
        return NotificationSerializer(notification).data
