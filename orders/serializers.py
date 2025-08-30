# orders/serializers.py
from rest_framework import serializers
from decimal import Decimal
from products.models import Product
from products.serializers import ProductSerializer
from .models import Order, OrderItem, ShippingAddress, CartItem
from orders.enums import DeliveryType
from products.enums import ProductStatus

# -------- Shipping Address Serializers --------
class ShippingAddressInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingAddress
        fields = [
            "full_name",
            "phone_number",
            "email",
            "street_address",
            "landmark",
            "apartment_name",
            "floor_number",
            "flat_number",
            "city",
            "zip_code",
            "billing_same_as_shipping",
        ]
        extra_kwargs = {
            "full_name": {"required": False, "allow_blank": True},
            "phone_number": {"required": False, "allow_blank": True},
            "street_address": {"required": False, "allow_blank": True},
            "city": {"required": False, "allow_blank": True},
            "zip_code": {"required": False, "allow_blank": True},
            "landmark": {"required": False, "allow_blank": True},
            "apartment_name": {"required": False, "allow_blank": True},
            "floor_number": {"required": False, "allow_blank": True},
            "flat_number": {"required": False, "allow_blank": True},
        }


class ShippingAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingAddress
        fields = [
            "id",
            "user",
            "full_name",
            "phone_number",
            "email",
            "street_address",
            "landmark",
            "apartment_name",
            "floor_number",
            "flat_number",
            "city",
            "zip_code",
            "billing_same_as_shipping",
        ]
        read_only_fields = ["id", "user"]


class ShippingAddressAttachSerializer(ShippingAddressInlineSerializer):
    order_id = serializers.IntegerField(write_only=True, required=True)

    class Meta(ShippingAddressInlineSerializer.Meta):
        fields = ["order_id"] + ShippingAddressInlineSerializer.Meta.fields


# -------- Order Items --------
class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    
    class Meta:
        model = OrderItem
        fields = ["id", "product", "quantity", "price"]










# # -------- Order Serializer --------
# class OrderSerializer(serializers.ModelSerializer):
#     items = OrderItemSerializer(many=True, read_only=True)
#     selected_shipping_address = ShippingAddressInlineSerializer(read_only=True)
#     selected_shipping_address_id = serializers.PrimaryKeyRelatedField(
#         source="selected_shipping_address",
#         queryset=ShippingAddress.objects.none(),
#         write_only=True,
#         required=False
#     )

#     order_status_display = serializers.CharField(source="get_order_status_display", read_only=True)
#     payment_status_display = serializers.CharField(source="get_payment_status_display", read_only=True)
#     delivery_type_display = serializers.CharField(source="get_delivery_type_display", read_only=True)
#     product_id = serializers

#     class Meta:
#         model = Order
#         fields = [
#             "id", "order_id",
#             "customer", "vendor",
#             "subtotal", "discount_amount", "promo_code",
#             "tax_amount", "delivery_fee", "total_amount",
#             "delivery_type", "delivery_type_display",
#             "delivery_instructions", "estimated_delivery", "delivery_date",
#             "selected_shipping_address", "selected_shipping_address_id",
#             "payment_method", "payment_status", "payment_status_display",
#             "order_status", "order_status_display",
#             "order_date", "item_count", "notes",
#             "items",
#             "created_at", "updated_at",
#         ]
#         read_only_fields = [
#             "order_id", "order_date", "items",
#             "subtotal", "tax_amount", "delivery_fee", "total_amount",
#             "item_count", "order_status", "payment_status",
#             "created_at", "updated_at",
#         ]

#     def validate_selected_shipping_address(self, value):
#         user = self.context["request"].user
#         if value and value.user != user:
#             raise serializers.ValidationError("This shipping address does not belong to you.")
#         return value

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         # Avoid circular import by local import
#         from users.serializers import UserSerializer
#         self.fields["customer"] = UserSerializer(read_only=True)
#         self.fields["vendor"] = UserSerializer(read_only=True)

#         request = self.context.get("request")
#         if request and request.user.is_authenticated:
#             self.fields["selected_shipping_address_id"].queryset = ShippingAddress.objects.filter(
#                 user=request.user
#             )








# -------- Order Serializer --------
class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    selected_shipping_address = ShippingAddressInlineSerializer(read_only=True)
    selected_shipping_address_id = serializers.PrimaryKeyRelatedField(
        source="selected_shipping_address",
        queryset=ShippingAddress.objects.none(),
        write_only=True,
        required=False
    )

    order_status_display = serializers.CharField(source="get_order_status_display", read_only=True)
    payment_status_display = serializers.CharField(source="get_payment_status_display", read_only=True)
    delivery_type_display = serializers.CharField(source="get_delivery_type_display", read_only=True)

    # <-- Added product_id field -->
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source="items",  # Will be used to create the OrderItem
        write_only=True,
        required=False
    )

    class Meta:
        model = Order
        fields = [
            "id", "order_id",
            "customer", "vendor",
            "subtotal", "discount_amount", "promo_code",
            "tax_amount", "delivery_fee", "total_amount",
            "delivery_type", "delivery_type_display",
            "delivery_instructions", "estimated_delivery", "delivery_date",
            "selected_shipping_address", "selected_shipping_address_id",
            "payment_method", "payment_status", "payment_status_display",
            "order_status", "order_status_display",
            "order_date", "item_count", "notes",
            "items",
            "product_id",  
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "order_id", "order_date", "items",
            "subtotal", "tax_amount", "delivery_fee", "total_amount",
            "item_count", "order_status", "payment_status",
            "created_at", "updated_at",
        ]

    def validate_selected_shipping_address(self, value):
        user = self.context["request"].user
        if value and value.user != user:
            raise serializers.ValidationError("This shipping address does not belong to you.")
        return value

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Avoid circular import by local import
        from users.serializers import UserSerializer
        self.fields["customer"] = UserSerializer(read_only=True)
        self.fields["vendor"] = UserSerializer(read_only=True)

        request = self.context.get("request")
        if request and request.user.is_authenticated:
            self.fields["selected_shipping_address_id"].queryset = ShippingAddress.objects.filter(
                user=request.user
            )







# -------- Cart --------
class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(status=ProductStatus.APPROVED.value, is_active=True),
        write_only=True,
        source="product"
    )

    class Meta:
        model = CartItem
        fields = ["id", "product", "product_id", "quantity", "price_snapshot"]
        read_only_fields = ["id", "price_snapshot"]

    def create(self, validated_data):
        user = self.context["request"].user
        product = validated_data["product"]
        quantity = validated_data.get("quantity", 1)
        price_snapshot = product.price1
        cart_item, created = CartItem.objects.update_or_create(
            user=user, product=product,
            defaults={"quantity": quantity, "price_snapshot": price_snapshot}
        )
        return cart_item

    def update(self, instance, validated_data):
        instance.quantity = validated_data.get("quantity", instance.quantity)
        instance.save(update_fields=["quantity"])
        return instance


# -------- Receipt Serializers --------
class ReceiptOrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    price = serializers.DecimalField(source="product.price1", max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ["product_name", "quantity", "price"]


class OrderReceiptSerializer(serializers.ModelSerializer):
    items = ReceiptOrderItemSerializer(many=True, read_only=True)
    shipping_address = ShippingAddressInlineSerializer(source="selected_shipping_address", read_only=True)

    customer_name = serializers.CharField(source="customer.get_full_name", read_only=True)
    vendor_name   = serializers.CharField(source="vendor.get_full_name", read_only=True)

    order_status_display   = serializers.CharField(source="get_order_status_display", read_only=True)
    payment_status_display = serializers.CharField(source="get_payment_status_display", read_only=True)
    delivery_type_display  = serializers.CharField(source="get_delivery_type_display", read_only=True)

    class Meta:
        model = Order
        fields = [
            "order_id", "order_date", "estimated_delivery",
            "customer_name", "vendor_name",
            "items", "subtotal", "discount_amount", "tax_amount", "delivery_fee", "total_amount",
            "delivery_type_display", "order_status_display", "payment_status_display",
            "payment_method", "shipping_address",
        ]
