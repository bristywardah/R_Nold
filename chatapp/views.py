from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import User
from chatapp.models import Message, Chat
from chatapp.serializers import MessageSerializer, ChatUserSerializer


class MessageSendAPIView(APIView):
    """Send a message to a user and broadcast via WebSocket"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        receiver = get_object_or_404(User, pk=pk)
        serializer = MessageSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        message = serializer.save(sender=request.user, receiver=receiver)

        # Ensure Chat exists both directions
        Chat.objects.get_or_create(sender=request.user, receiver=receiver)
        Chat.objects.get_or_create(sender=receiver, receiver=request.user)

        # Broadcast to both users
        payload = MessageSerializer(message, context={'request': request}).data
        channel_layer = get_channel_layer()
        for uid in {request.user.id, receiver.id}:
            async_to_sync(channel_layer.group_send)(
                f"chat_{uid}",
                {"type": "chat_message", "message": payload}
            )

        return Response(payload, status=status.HTTP_201_CREATED)


class ChatMessagesListView(generics.ListAPIView):
    """List all messages between auth user and another user"""
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return Message.objects.none()
        user_id = self.kwargs.get('pk')
        get_object_or_404(User, pk=user_id)
        return Message.objects.filter(
            Q(sender=self.request.user, receiver_id=user_id) |
            Q(sender_id=user_id, receiver=self.request.user),
            is_deleted=False
        ).select_related('sender', 'receiver').order_by('timestamp')


class UserChatsListView(APIView):
    """List all users the authenticated user has chats with"""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        chats = Chat.objects.filter(Q(sender=user) | Q(receiver=user)).order_by('-created_at')

        users = set()
        for chat in chats:
            other = chat.receiver if chat.sender == user else chat.sender
            users.add(other)

        serializer = ChatUserSerializer(list(users), many=True, context={'request': request})
        return Response(serializer.data)


class MessageDeleteView(generics.DestroyAPIView):
    """Soft delete a message if sender is the auth user"""
    queryset = Message.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]

    def get_object(self):
        obj = get_object_or_404(Message, pk=self.kwargs.get('pk'), is_deleted=False)
        if obj.sender != self.request.user:
            raise PermissionDenied("You do not have permission to delete this message.")
        return obj

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save()

    def destroy(self, request, *args, **kwargs):
        self.perform_destroy(self.get_object())
        return Response({"detail": "Message deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


class MessageUpdateView(generics.UpdateAPIView):
    """Edit a message sent by auth user"""
    queryset = Message.objects.select_related('sender').all()
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['patch']

    def get_object(self):
        obj = get_object_or_404(Message, pk=self.kwargs.get('pk'), is_deleted=False)
        if obj.sender != self.request.user:
            raise PermissionDenied("You do not have permission to edit this message.")
        return obj

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        new_content = request.data.get('message')
        if not new_content:
            return Response({"detail": "field 'message' is required"}, status=status.HTTP_400_BAD_REQUEST)

        instance.message = new_content
        instance.is_edited = True
        instance.save()

        # Broadcast the edit
        payload = MessageSerializer(instance, context={'request': request}).data
        channel_layer = get_channel_layer()
        for uid in {instance.sender_id, instance.receiver_id}:
            async_to_sync(channel_layer.group_send)(
                f"chat_{uid}",
                {"type": "chat_message", "message": payload}
            )

        return Response({"detail": "Message edited successfully."}, status=status.HTTP_200_OK)


class MessageListCreateView(generics.ListCreateAPIView):
    """List all messages with a user / Create message to a user"""
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user_id = self.kwargs.get('pk')
        get_object_or_404(User, pk=user_id)
        return Message.objects.filter(
            Q(sender=self.request.user, receiver_id=user_id) |
            Q(sender_id=user_id, receiver=self.request.user),
            is_deleted=False
        ).select_related('sender', 'receiver').order_by('timestamp')

    def perform_create(self, serializer):
        receiver_id = self.kwargs.get('pk')
        receiver = get_object_or_404(User, pk=receiver_id)
        message = serializer.save(sender=self.request.user, receiver=receiver)

        # Ensure Chat exists both directions
        Chat.objects.get_or_create(sender=self.request.user, receiver=receiver)
        Chat.objects.get_or_create(sender=receiver, receiver=self.request.user)

        # Broadcast via WebSocket
        payload = MessageSerializer(message, context={'request': self.request}).data
        channel_layer = get_channel_layer()
        for uid in {self.request.user.id, receiver.id}:
            async_to_sync(channel_layer.group_send)(
                f"chat_{uid}",
                {"type": "chat_message", "message": payload}
            )
