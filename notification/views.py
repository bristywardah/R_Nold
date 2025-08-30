from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import DestroyAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from users.models import User
from users.enums import UserRole
from .models import Notification
from .serializers import NotificationSerializer
from .utils import send_notification_to_user


# ----------------------------
# Notification List
# ----------------------------
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notification_list(request):
    user = request.user

    if getattr(user, "role", None) == UserRole.ADMIN.value or user.is_staff:
        # Admin sees all product notifications
        qs = Notification.objects.filter(meta_data__type="product").order_by("-event_time")
    elif getattr(user, "role", None) == UserRole.VENDOR.value:
        # Vendor sees only own product notifications
        qs = user.notifications.filter(meta_data__type="product").order_by("-event_time")
    else:
        # Customer sees all own notifications
        qs = user.notifications.all().order_by("-event_time")

    serializer = NotificationSerializer(qs, many=True)
    return Response(serializer.data)


# ----------------------------
# Unseen Notification List
# ----------------------------
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def unseen_notification_list(request):
    user = request.user

    if getattr(user, "role", None) == UserRole.ADMIN.value or user.is_staff:
        # Admin sees all unseen product notifications
        qs = Notification.objects.filter(meta_data__type="product", seen=False).order_by("-event_time")
    elif getattr(user, "role", None) == UserRole.VENDOR.value:
        # Vendor sees only own unseen product notifications
        qs = user.notifications.filter(meta_data__type="product", seen=False).order_by("-event_time")
    else:
        # Customer sees own unseen notifications
        qs = user.notifications.filter(seen=False).order_by("-event_time")

    serializer = NotificationSerializer(qs, many=True)
    return Response(serializer.data)


# ----------------------------
# Mark Notification as Seen
# ----------------------------
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_notification_seen(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    if not notification.seen:
        notification.seen = True
        notification.save(update_fields=["seen"])
    serializer = NotificationSerializer(notification)
    return Response(serializer.data)


# ----------------------------
# Delete Notification
# ----------------------------
class NotificationDeleteAPIView(DestroyAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()

        user = self.request.user
        if not hasattr(user, "notifications"):
            raise PermissionDenied("User has no notifications attribute.")

        return user.notifications.all()


# ----------------------------
# Hit Notify (Testing)
# ----------------------------
@api_view(["GET"])
@permission_classes([AllowAny])
def hit_notify(request, email):
    user = get_object_or_404(User, email=email)
    send_notification_to_user(
        user=user,
        message=f"Hello {email}",
        ntype="sms",  # example type
        sender=None,
        meta_data={"info": "test notification"}
    )
    return JsonResponse({"message": "notification sent"})
