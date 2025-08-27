from rest_framework import serializers
from payments.models import Payment
from orders.models import Order


class PaymentSerializer(serializers.ModelSerializer):
    order_id = serializers.CharField(write_only=True, required=True)
    vendor_name = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id",
            "order_id",
            "order",
            "vendor",
            "vendor_name",
            "customer",
            "customer_name",
            "amount",
            "payment_method",
            "transaction_id",
            "status",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "vendor",
            "order",
            "status",
            "transaction_id",
            "created_at",
            "updated_at"
        ]

    def get_vendor_name(self, obj):
        return obj.vendor.get_full_name() if obj.vendor else None

    def get_customer_name(self, obj):
        return obj.customer.get_full_name() if obj.customer else None

    def create(self, validated_data):
        request = self.context.get("request")
        user = request.user if request else None

        # Customer auto-assign
        if user and getattr(user, "role", None) == "customer":
            validated_data["customer"] = user

        # Link to order
        order_id = validated_data.pop("order_id")
        order = Order.objects.filter(order_id=order_id, customer=user).first()
        if not order:
            raise serializers.ValidationError({"detail": "Order not found."})

        validated_data["order"] = order
        validated_data["vendor"] = order.vendor
        validated_data["amount"] = order.total_amount

        return super().create(validated_data)



