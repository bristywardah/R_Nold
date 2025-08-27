import base64
import datetime
from django.core.files.base import ContentFile
from rest_framework import serializers
from .models import Message, Chat


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
        representation = super().to_representation(instance)
        if instance.attachment and instance.attachment.path:
            try:
                with open(instance.attachment.path, 'rb') as file:
                    encoded_file = base64.b64encode(file.read()).decode('utf-8')
                    representation['attachment_base64'] = f"{instance.mime_type},{encoded_file}"
            except FileNotFoundError:
                representation['attachment_base64'] = None
        return representation

    def get_attachment_url(self, instance):
        request = self.context.get('request')
        if instance.attachment and hasattr(instance.attachment, 'url'):
            return request.build_absolute_uri(instance.attachment.url) if request else instance.attachment.url
        return None

    def to_internal_value(self, data):
        if 'attachment_base64' in data and data['attachment_base64']:
            try:
                mime_type, file_data = data['attachment_base64'].split(',', 1)
                decoded_file_data = base64.b64decode(file_data)
                file_name = data.get('attachment_name') or f"file_{int(datetime.datetime.now().timestamp())}"
                content_file = ContentFile(decoded_file_data, name=file_name)
                data['attachment'] = content_file
                data['mime_type'] = mime_type
            except Exception:
                raise serializers.ValidationError({'attachment_base64': 'Invalid base64 format.'})
        return super().to_internal_value(data)


class ChatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chat
        fields = ['id', 'sender', 'receiver', 'created_at']
        read_only_fields = ['id', 'created_at', 'sender']
