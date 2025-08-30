from django.conf import settings
from django.db import models
from rest_framework.exceptions import ValidationError
from users.models import BaseModel


class Chat(BaseModel):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chats_sent')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chats_received')
    offer = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='chats', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('sender', 'receiver', 'offer')


class Message(BaseModel):
    MAX_FILE_SIZE = 20 * 1024 * 1024  

    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_messages')
    message = models.TextField(default="", null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    reply_to = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')

    attachment = models.FileField(null=True, blank=True)
    attachment_url = models.URLField(max_length=500, blank=True, null=True)
    attachment_name = models.CharField(max_length=255, blank=True, null=True)
    mime_type = models.CharField(max_length=300, blank=True, null=True)

    is_read = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    is_edited = models.BooleanField(default=False)
    is_reported = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.attachment and self.attachment.size > self.MAX_FILE_SIZE:
            raise ValidationError(f"The file size exceeds the {self.MAX_FILE_SIZE / (1024 * 1024)} MB limit.")
        super().clean()

    def __str__(self):
        return f"{self.sender.email} → {self.receiver.email} | {self.message[:20]}"
