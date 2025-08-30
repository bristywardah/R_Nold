from rest_framework import serializers
from .models import PayoutRequest
from payments.models import Payment
from payments.enums import PaymentStatusEnum
from django.db import models
from orders.models import Order
from dashboard.models import Alert
from users.models import User
from orders.models import OrderItem
from django.db.models import Sum


class PayoutRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayoutRequest
        fields = ["id", "vendor", "amount", "payment_method", "note", "status", "created_at"]
        read_only_fields = ["id", "vendor", "status", "created_at"]

    def validate_amount(self, value):
        user = self.context["request"].user
        total_earnings = Payment.objects.filter(
            vendor=user,
            status=PaymentStatusEnum.COMPLETED.value
        ).aggregate(total=models.Sum("amount"))["total"] or 0

        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0.")
        if value > total_earnings:
            raise serializers.ValidationError("Amount exceeds your total earnings.")
        return value

    def create(self, validated_data):
        validated_data["vendor"] = self.context["request"].user
        return super().create(validated_data)




class LatestOrderSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ["id", "order_id", "customer_name", "order_date", "order_status"]

    def get_customer_name(self, obj):
        name_method = getattr(obj.customer, "get_full_name", None)
        if callable(name_method):
            return name_method()
        return getattr(obj.customer, "email", str(obj.customer))









class AlertSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    stock_quantity = serializers.IntegerField(source="product.stock_quantity", read_only=True)

    class Meta:
        model = Alert
        fields = ["id", "product", "product_name", "stock_quantity", "message", "created_at"]











class VendorPerformanceSerializer(serializers.ModelSerializer):
    products_sold = serializers.SerializerMethodField()
    revenue = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "first_name", "last_name", "email", "products_sold", "revenue", "status"]

    def get_products_sold(self, obj):
        return OrderItem.objects.filter(
            order__vendor=obj,
            status="completed"  # or use your OrderStatusEnum.COMPLETED.value
        ).aggregate(total=Sum("quantity"))["total"] or 0

    def get_revenue(self, obj):
        return Payment.objects.filter(
            vendor=obj,
            status=PaymentStatusEnum.COMPLETED.value
        ).aggregate(total=Sum("amount"))["total"] or 0

    def get_status(self, obj):
        return "Active" if obj.is_active else "Inactive"
