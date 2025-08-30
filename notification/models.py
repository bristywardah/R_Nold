from django.db import models
from django.conf import settings
from users.models import User
from django.db.models import JSONField


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_notifications', null=True, blank=True)
    event_time = models.DateTimeField(auto_now_add=True)
    message = models.TextField()
    seen = models.BooleanField(default=False)
    path = models.CharField(max_length=255, null=True, blank=True)
    meta_data = JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)




