from django.urls import path
from .views import (
    MessageSendAPIView,
    ChatMessagesListView,
    UserChatsListView,
    MessageDeleteView,
    MessageUpdateView,
    MessageListCreateView,
)

urlpatterns = [
    path("messages/<int:pk>/send/", MessageSendAPIView.as_view(), name="message-send"),

    path("messages/<int:pk>/", ChatMessagesListView.as_view(), name="chat-messages"),

    path("chats/", UserChatsListView.as_view(), name="user-chats"),

    path("messages/<int:pk>/delete/", MessageDeleteView.as_view(), name="message-delete"),

    path("messages/<int:pk>/edit/", MessageUpdateView.as_view(), name="message-update"),

    path("messages/", MessageListCreateView.as_view(), name="message-list"),
]
