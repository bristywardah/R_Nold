import base64
import datetime
from django.core.files.base import ContentFile
from rest_framework import serializers
from .models import Message
from django.conf import settings
from users.models import User

class MessageSerializer(serializers.ModelSerializer):
    attachment_base64 = serializers.CharField(write_only=True, required=False, allow_blank=True)
    attachment_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Message
        fields = [
            'id', 'sender', 'receiver', 'message', 'timestamp', 'reply_to',
            'attachment', 'attachment_base64', 'attachment_name', 'mime_type',
            'attachment_url',
            'is_read', 'is_deleted', 'is_edited', 'is_reported'
        ]
        read_only_fields = ['id', 'timestamp', 'sender']

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if instance.attachment and hasattr(instance.attachment, 'path'):
            try:
                with open(instance.attachment.path, 'rb') as file:
                    encoded = base64.b64encode(file.read()).decode()
                    rep['attachment_base64'] = f"{instance.mime_type},{encoded}"
            except FileNotFoundError:
                rep['attachment_base64'] = None
        return rep

    def get_attachment_url(self, instance):
        request = self.context.get('request')
        if instance.attachment and hasattr(instance.attachment, 'url'):
            return request.build_absolute_uri(instance.attachment.url) if request else instance.attachment.url
        return None

    def to_internal_value(self, data):
        if data.get('attachment_base64'):
            try:
                mime_type, file_data = data['attachment_base64'].split(',', 1)
                decoded = base64.b64decode(file_data)
                filename = data.get('attachment_name') or f"file_{int(datetime.datetime.now().timestamp())}"
                data['attachment'] = ContentFile(decoded, name=filename)
                data['mime_type'] = mime_type
            except Exception:
                raise serializers.ValidationError({'attachment_base64': 'Invalid base64 format.'})
        return super().to_internal_value(data)









class ChatUserSerializer(serializers.ModelSerializer):
    user_image = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'user_image']

    def get_user_image(self, obj):
        request = self.context.get('request')
        if obj.profile_image:
            return request.build_absolute_uri(obj.profile_image.url) if request else obj.profile_image.url
        return None

    def get_name(self, obj):
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        return full_name if full_name else obj.email.split('@')[0]
