# # serializers.py

# from rest_framework import serializers
# from .models import Notification

# class NotificationSerializer(serializers.ModelSerializer):
#     sender = serializers.CharField(source='user.email', read_only=True)
#     full_name = serializers.SerializerMethodField()
#     meta_data = serializers.JSONField(required=False)

#     class Meta:
#         model = Notification
#         fields = ['id', 'sender', 'event_time', 'message', 'seen', 'full_name', 'meta_data']
#         read_only_fields = ['id', 'event_time']

#     def get_full_name(self, obj):
#         if obj.user.role == 'VENDOR' and hasattr(obj.user, ''):
#             return obj.user.companyprofile.company_name
#         elif obj.user.role == 'CUSTOMER' and hasattr(obj.user, ''):
#             return obj.user.CUSTOMER.
#         elif obj.user.first_name or obj.user.last_name:
#             return f"{obj.user.first_name} {obj.user.last_name}".strip()
#         return None

    





from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    sender_email = serializers.EmailField(source="sender.email", read_only=True)
    full_name = serializers.SerializerMethodField()
    meta_data = serializers.JSONField(required=False)

    class Meta:
        model = Notification
        fields = [
            "id",
            "sender_email",
            "event_time",
            "message",
            "seen",
            "full_name",
            "meta_data",
        ]
        read_only_fields = ["id", "event_time"]

    def get_full_name(self, obj):
        """
        Return full_name depending on user role:
        - Vendor → show 'Vendor: <first last>'
        - Customer → show 'Customer: <first last>'
        - Admin → show 'Admin: <first last>'
        """
        user = obj.sender or obj.user
        if not user:
            return None

        role = user.role.lower() if user.role else ""

        name = f"{user.first_name} {user.last_name}".strip()
        if not name:
            name = user.email

        if role == "vendor":
            return f"Vendor: {name}"
        elif role == "customer":
            return f"Customer: {name}"
        elif role == "admin":
            return f"Admin: {name}"
        return name
