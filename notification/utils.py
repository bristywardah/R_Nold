from __future__ import annotations

from typing import Optional, Dict, Any
from dataclasses import dataclass
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.db import transaction

from users.models import User
from notification.models import Notification
from orders.models import Order
from django.db import models


# Try to align with your Enum (used by NotificationConsumer). Fallback to strings if not available.
try:
    from users.enums import UserRole
    _ROLE_ADMIN = UserRole.ADMIN.value
    _ROLE_VENDOR = UserRole.VENDOR.value
    _ROLE_CUSTOMER = getattr(UserRole, "CUSTOMER", None)
    _ROLE_CUSTOMER = _ROLE_CUSTOMER.value if _ROLE_CUSTOMER else "customer"
except Exception:  # pragma: no cover
    _ROLE_ADMIN = "admin"
    _ROLE_VENDOR = "vendor"
    _ROLE_CUSTOMER = "customer"


# ---------------------------
# Notification Types
# ---------------------------
class NotificationType:
    CHAT = "chat"
    ORDER = "order"
    PAYMENT = "payment"
    SELLER_APPLICATION = "seller_application"
    SMS = "sms"
    PRODUCT = "product"


# ---------------------------
# Helpers
# ---------------------------
def _role_label(user: Optional[User]) -> str:
    if not user or not getattr(user, "role", None):
        return ""
    return str(user.role).capitalize()


def _display_name(user: Optional[User]) -> str:
    if not user:
        return ""
    name = f"{(user.first_name or '').strip()} {(user.last_name or '').strip()}".strip()
    return name or user.email or f"User#{user.id}"


def _base_payload(notification: Notification, target_user: User, full_name_from: Optional[User]) -> Dict[str, Any]:
    full_name_user = full_name_from or target_user
    return {
        "id": notification.id,
        "message": notification.message,
        "event_time": notification.event_time.isoformat(),
        "seen": notification.seen,
        "full_name": f"{_role_label(full_name_user)}: {_display_name(full_name_user)}".strip(": "),
        "role": _role_label(full_name_user),
        "meta_data": notification.meta_data or {},
    }


def _group_name_for_user(user: User) -> str:
    role = (getattr(user, "role", "") or "").lower()
    if role == _ROLE_ADMIN or getattr(user, "is_staff", False):
        return "notifications_admins"
    if role == _ROLE_VENDOR:
        return f"notifications_vendor_{user.id}"
    return f"notifications_user_{user.id}"


def _safe_group_send(group_name: str, payload: Dict[str, Any]) -> None:
    """
    Fire-and-forget group_send; never raise to caller.
    """
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            return  # channel layer not configured (e.g., tests)
        async_to_sync(channel_layer.group_send)(group_name, payload)
    except Exception:
        # Intentionally swallow errors so DB notification creation is never blocked by WS infra.
        # You can add logging here if desired.
        # import logging; logging.getLogger(__name__).exception("group_send failed")
        pass


def prepare_notification_meta_data(
    *,
    ntype: str,
    sender: Optional[User] = None,
    base_meta_data: Optional[Dict[str, Any]] = None,
    extras: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    meta: Dict[str, Any] = {}
    if base_meta_data:
        meta.update(base_meta_data)

    meta["type"] = ntype
    if sender:
        meta["sender_id"] = str(sender.id)
        meta["sender_email"] = sender.email

    # Type-specific defaults
    if ntype == NotificationType.CHAT:
        meta.setdefault("chat_type", "direct")
    elif ntype == NotificationType.ORDER:
        meta.setdefault("order_id", None)
        meta.setdefault("order_status", None)
    elif ntype == NotificationType.PAYMENT:
        meta.setdefault("payment_id", None)
        meta.setdefault("payment_status", None)
    elif ntype == NotificationType.SELLER_APPLICATION:
        meta.setdefault("application_id", None)
        meta.setdefault("application_status", None)
    elif ntype == NotificationType.SMS:
        meta.setdefault("to_user_id", None)
        meta.setdefault("text_preview", None)
    elif ntype == NotificationType.PRODUCT:
        meta.setdefault("product_id", None)
        meta.setdefault("product_name", None)
        meta.setdefault("action", "created")

    if extras:
        meta.update(extras)

    return meta







# ---------------------------------------------
# Core send function
# ---------------------------------------------
def send_notification_to_user(
    user: User,
    message: str,
    *,
    ntype: str,
    sender: Optional[User] = None,
    meta_data: Optional[Dict[str, Any]] = None,
) -> Notification:

    assert isinstance(user, User), "user must be a User instance"
    if sender:
        assert isinstance(sender, User), "sender must be a User instance"

    notification_meta = prepare_notification_meta_data(
        ntype=ntype, sender=sender, extras=meta_data or {}
    )

    with transaction.atomic():
        notification = Notification.objects.create(
            user=user,
            sender=sender,
            message=message,
            meta_data=notification_meta,
            event_time=timezone.now(),
        )

    payload = _base_payload(notification, target_user=user, full_name_from=sender or user)
    group_name = _group_name_for_user(user)

    _safe_group_send(
        group_name,
        {"type": "send_notification", "notification": payload},
    )

    return notification











# ---------------------------------------------
# Order payment success
# ---------------------------------------------
def notify_order_payment_completed(order: Order, sender: Optional[User] = None) -> None:
    """
    Send notifications to customer, vendor, and admins when order payment is completed.
    """
    meta = {
        "order_id": str(order.order_id),
        "total_amount": str(order.total_amount),
        "vendor_id": str(order.vendor.id),
        "customer_id": str(order.customer.id),
    }

    send_notification_to_user(
        order.customer,
        f"Your payment for order #{order.order_id} was successful.",
        ntype=NotificationType.ORDER,
        sender=sender or order.vendor,
        meta_data=meta,
    )

    send_notification_to_user(
        order.vendor,
        f"You have received a paid order #{order.order_id} from {order.customer.email}.",
        ntype=NotificationType.ORDER,
        sender=sender or order.customer,
        meta_data=meta,
    )

    admins = User.objects.filter(role=_ROLE_ADMIN, is_active=True)
    for admin in admins:
        send_notification_to_user(
            admin,
            f"Order #{order.order_id} has been paid by {order.customer.email} for vendor {order.vendor.email}.",
            ntype=NotificationType.ORDER,
            sender=sender or order.customer,
            meta_data=meta,
        )









# ---------------------------------------------
# Order payment cancelled/expired
# ---------------------------------------------
def notify_order_payment_cancelled(order: Order, sender: Optional[User] = None) -> None:
    """
    Send notifications when order payment is cancelled or expired.
    """
    meta = {
        "order_id": str(order.order_id),
        "total_amount": str(order.total_amount),
        "vendor_id": str(order.vendor.id),
        "customer_id": str(order.customer.id),
    }

    send_notification_to_user(
        order.customer,
        f"Your payment for order #{order.order_id} was cancelled or expired.",
        ntype=NotificationType.ORDER,
        sender=sender or order.vendor,
        meta_data=meta,
    )

    send_notification_to_user(
        order.vendor,
        f"Payment for order #{order.order_id} from {order.customer.email} was cancelled/expired.",
        ntype=NotificationType.ORDER,
        sender=sender or order.customer,
        meta_data=meta,
    )

    admins = User.objects.filter(role=_ROLE_ADMIN, is_active=True)
    for admin in admins:
        send_notification_to_user(
            admin,
            f"Order #{order.order_id} payment failed/cancelled by {order.customer.email} (vendor: {order.vendor.email}).",
            ntype=NotificationType.ORDER,
            sender=sender or order.customer,
            meta_data=meta,
        )







# ---------------------------------------------
# Chat notification wrapper
# ---------------------------------------------
@database_sync_to_async
def create_chat_notification(receiver: User, msg) -> Notification:
    preview = (msg.message or "")
    if len(preview) > 50:
        preview = preview[:47] + "..."

    return send_notification_to_user(
        user=receiver,
        message=f"New message from {_display_name(msg.sender)}: {preview}",
        ntype=NotificationType.CHAT,
        sender=msg.sender,
        meta_data={
            "message_id": str(msg.id),
            "sender_id": str(msg.sender.id),
            "receiver_id": str(receiver.id),
            "chat_type": "direct",
        },
    )











def notify_vendor_order_payment(
    vendor: User,
    *,
    order_id: str,
    amount: float,
    order_status: str,
    payment_method: str,
    sender: Optional[User] = None,
) -> Notification:
    meta_data = {
        "request_date": timezone.now().strftime("%Y-%m-%d"),
        "amount": str(amount),
        "order_status": order_status,
        "payment_method": payment_method,
        "order_id": order_id,
    }
    return send_notification_to_user(
        user=vendor,
        message=f"Order #{order_id} payment update.",
        ntype=NotificationType.ORDER,
        sender=sender,
        meta_data=meta_data,
    )