from rest_framework import serializers
from users.models import User, SellerApplication
from django.utils import timezone
from datetime import timedelta
from users.enums import SellerApplicationStatus
import random, string
from payments.models import Payment
from orders.models import Order
from products.models import Product
from django.db.models import Count, Avg, Sum
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.password_validation import validate_password





# --------------------------
# USER SERIALIZERS
# --------------------------

class UserSerializer(serializers.ModelSerializer):
    profile_image = serializers.ImageField(allow_null=True, required=False)
    cover_image = serializers.ImageField(allow_null=True, required=False)
    phone_number = serializers.CharField(allow_null=True, required=False)
    secondary_number = serializers.CharField(allow_null=True, required=False)
    emergency_contact = serializers.CharField(allow_null=True, required=False)
    address = serializers.CharField(allow_null=True, required=False)
    gender = serializers.CharField(allow_null=True, required=False)
    date_of_birth = serializers.DateField(allow_null=True, required=False)
    national_id = serializers.CharField(allow_null=True, required=False)
    is_online = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'profile_image', 'cover_image',
            'phone_number', 'secondary_number', 'emergency_contact', 'address', 'gender',
            'date_of_birth', 'national_id', 'role', 'is_online'
        ]








class UserSignupSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(write_only=True)
    agree_to_terms = serializers.BooleanField(write_only=True)
    role = serializers.CharField(read_only=True, default='customer')

    class Meta:
        model = User
        fields = ['email', 'password', 'full_name', 'agree_to_terms', 'role']
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def validate_agree_to_terms(self, value):
        if not value:
            raise serializers.ValidationError("You must agree to the terms.")
        return value

    def create(self, validated_data):
        full_name = validated_data.pop('full_name')
        first_name, *last_name = full_name.split(' ', 1)
        last_name = last_name[0] if last_name else ''
        password = validated_data.pop('password')

        user = User(
            email=validated_data['email'],
            first_name=first_name,
            last_name=last_name,
            role='customer'
        )
        user.set_password(password)
        user.save()
        return user





class UserLoginSerializer(serializers.Serializer):
    # Either login with email/password
    email = serializers.EmailField(required=False)
    password = serializers.CharField(write_only=True, required=False)
    # Or login with Firebase
    id_token = serializers.CharField(write_only=True, required=False)

    def validate(self, data):
        if not data.get("id_token") and not (data.get("email") and data.get("password")):
            raise serializers.ValidationError(
                "You must provide either id_token (Firebase) or email and password."
            )
        return data


class UserLoginResponseSerializer(serializers.Serializer):
    user = UserSerializer(read_only=True) 
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()











class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'profile_image', 'cover_image',
            'phone_number', 'secondary_number', 'emergency_contact',
            'address', 'gender', 'date_of_birth', 'national_id'
        ]
        read_only_fields = ['email', 'role']


# --------------------------
# USER PUBLIC SERIALIZER
# --------------------------

class UserPublicSerializer(serializers.ModelSerializer):
    profile_image_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'first_name',
            'last_name',
            'profile_image_url',
            'role',
        ]

        read_only_field = ['role']

    def get_profile_image_url(self, obj):
        request = self.context.get('request')
        if obj.profile_image and hasattr(obj.profile_image, 'url'):
            return request.build_absolute_uri(obj.profile_image.url) if request else obj.profile_image.url
        return None








# --------------------------
# SELLER APPLICATION SERIALIZERS
# --------------------------

class SellerApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerApplication
        exclude = ['verification_code', 'created_at', 'updated_at', 'first_name', 'last_name', 'owner_images', 'email']
        read_only_fields = ['status', 'user']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class SellerApplicationAdminUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerApplication
        fields = ['status']

    def validate_status(self, value):
        allowed_statuses = [
            SellerApplicationStatus.APPROVED.value,
            SellerApplicationStatus.REJECTED.value,
        ]
        if value not in allowed_statuses:
            raise serializers.ValidationError(
                f"Status must be one of: {', '.join(allowed_statuses)}"
            )
        return value

    def update(self, instance, validated_data):
        old_status = instance.status
        new_status = validated_data['status']

        if old_status == new_status:
            raise serializers.ValidationError("Status is already set to this value.")

        # Generate verification code if approved
        if new_status == SellerApplicationStatus.APPROVED.value:
            instance.verification_code = ''.join(
                random.choices(string.ascii_uppercase + string.digits, k=6)
            )
            # Also change user role to vendor
            instance.user.role = "vendor"
            instance.user.save()

        instance.status = new_status
        instance.updated_at = timezone.now()
        instance.save()
        return instance






# --------------------------
# CUSTOMER LIST SERIALIZER
# --------------------------

class CustomerListSerializer(serializers.ModelSerializer):
    user_id = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    signup_date = serializers.DateTimeField(source="created_at", format="%Y-%m-%d")
    last_activity = serializers.DateTimeField(source="last_login", format="%Y-%m-%d %H:%M", allow_null=True)
    actions = serializers.SerializerMethodField()
    total_orders = serializers.SerializerMethodField()
    total_spend = serializers.SerializerMethodField()
    is_active = serializers.BooleanField()

    class Meta:
        model = User
        fields = [
            "id",
            "user_id", "customer_name", "customer_email", "payment_status",
            "signup_date", "last_activity", "actions",
            "total_orders", "total_spend", "is_active",
        ]

    def get_user_id(self, obj):
        return f"Wrioko{1000 + obj.id}"

    def get_customer_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()

    def get_customer_email(self, obj):
        return obj.email

    def get_payment_status(self, obj):
        from payments.models import Payment
        last_payment = Payment.objects.filter(customer=obj).order_by("-created_at").first()
        return last_payment.status if last_payment else "N/A"

    def get_actions(self, obj):
        return {
            "view_url": f"/admin/customers/{obj.id}/view",
            "delete_url": f"/admin/customers/{obj.id}/delete"
        }

    def get_total_orders(self, obj):
        from orders.models import Order
        return Order.objects.filter(customer=obj).count()

    def get_total_spend(self, obj):
        from orders.models import Order
        total = Order.objects.filter(customer=obj).aggregate(total=Sum("total_amount"))["total"]
        return total or 0










# --------------------------
# CUSTOMER DETAIL SERIALIZER
# --------------------------

class CustomerDetailSerializer(UserSerializer):
    orders = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ["orders"]

    def get_orders(self, obj):
        # Lazy import to avoid circular import
        from orders.serializers import OrderReceiptSerializer
        orders = Order.objects.filter(customer=obj).order_by("-created_at")
        return OrderReceiptSerializer(orders, many=True).data


# --------------------------
# VENDOR LIST SERIALIZER
# --------------------------

class VendorListSerializer(serializers.ModelSerializer):
    user_id = serializers.SerializerMethodField()
    vendor_name = serializers.SerializerMethodField()
    approval_status = serializers.CharField(source="seller_application.status", default="N/A")
    products_count = serializers.SerializerMethodField()
    orders_count = serializers.SerializerMethodField()
    ratings = serializers.SerializerMethodField()
    signup_date = serializers.DateTimeField(source="created_at", format="%Y-%m-%d")
    last_activity = serializers.DateTimeField(source="last_login", format="%Y-%m-%d %H:%M", allow_null=True)
    actions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "user_id", "vendor_name", "approval_status",
            "products_count", "orders_count", "ratings",
            "signup_date", "last_activity", "actions"
        ]

    def get_user_id(self, obj):
        return f"Wrioko{1000 + obj.id}"

    def get_vendor_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()

    def get_products_count(self, obj):
        return Product.objects.filter(vendor=obj).count()

    def get_orders_count(self, obj):
        return Order.objects.filter(vendor=obj).count()


    def get_actions(self, obj):
        return {
            "view_url": f"/admin/vendors/{obj.id}/view",
            "delete_url": f"/admin/vendors/{obj.id}/delete"
        }







class OTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email does not exist.")
        return value


class SendOTPResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    email = serializers.EmailField()

    class Meta:
        ref_name = "SendOTPResponse"


class ErrorResponseSerializer(serializers.Serializer):
    error = serializers.CharField()
    detail = serializers.CharField(required=False, allow_null=True)

    class Meta:
        ref_name = "GenericErrorResponse"


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(min_length=6, max_length=6, required=True)

    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must be numeric.")
        return value


class VerifyOTPResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    email = serializers.EmailField()

    class Meta:
        ref_name = "VerifyOTPResponse"


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, min_length=8, required=True)

    def validate_new_password(self, value):
        try:
            validate_password(value, user=self.context.get('request', {}).user)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value


class ChangePasswordResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    full_name = serializers.CharField()

    class Meta:
        ref_name = "ChangePasswordResponse"




class SetNewPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    new_password = serializers.CharField(write_only=True, min_length=8, required=True)
    confirm_password = serializers.CharField(write_only=True, min_length=8, required=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        try:
            validate_password(data['new_password'])
        except DjangoValidationError as e:
            raise serializers.ValidationError({'new_password': list(e.messages)})

        return data

    class Meta:
        ref_name = "SetNewPassword"




class MessageResponseSerializer(serializers.Serializer):
    message = serializers.CharField()

    class Meta:
        ref_name = "MessageResponse"











class FirebaseLoginSerializer(serializers.Serializer):
    id_token = serializers.CharField(required=True)





