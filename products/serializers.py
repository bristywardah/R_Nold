from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone
from products.models import Product, ProductImage, Promotion
from common.models import Category, Tag, SEO
from products.enums import DiscountType
from django.db.models import Q
from products.models import ReturnProduct, ProductSpecifications
from common.models import ImageUpload
from users.enums import UserRole
from orders.models import OrderItem
from orders.enums import OrderStatus
from users.serializers import UserSerializer


class PromotionSerializer(serializers.ModelSerializer):
    products = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), many=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = Promotion
        fields = [
            "id", "name", "discount_type", "discount_value", "products",
            "start_datetime", "end_datetime", "description",
            "is_active", "status",
        ]

    def get_status(self, obj):
        return obj.status

    def validate(self, attrs):
        if attrs["discount_type"] == DiscountType.PERCENTAGE.value:
            if attrs["discount_value"] < 0 or attrs["discount_value"] > 100:
                raise serializers.ValidationError(
                    {"discount_value": "Percentage discount must be between 0 and 100."}
                )
        if attrs["end_datetime"] <= attrs["start_datetime"]:
            raise serializers.ValidationError(
                {"end_datetime": "End date must be after start date."}
            )
        return attrs







class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image", "created_at"]



class ProductSpecificationsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSpecifications
        fields = [
            "dimensions",
            "material",
            "color",
            "weight",
            "assembly_required",
            "warranty",
            "care_instructions",
            "country_of_origin",
        ]



class ProductSerializer(serializers.ModelSerializer):
    prod_id = serializers.CharField(read_only=True)
    vendor = serializers.HiddenField(default=serializers.CurrentUserDefault())
    vendor_id = serializers.IntegerField(source="vendor.id", read_only=True)
    vendor_details = UserSerializer(source="vendor", read_only=True)
    categories = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Category.objects.all(), required=False
    )
    tags = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Tag.objects.all(), required=False
    )
    seo = serializers.PrimaryKeyRelatedField(
        queryset=SEO.objects.all(), required=False, allow_null=True
    )
    images = ProductImageSerializer(many=True, read_only=True)
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False
    )
    specifications = ProductSpecificationsSerializer(required=False)



    class Meta:
        model = Product
        fields = [
            "id", "prod_id", "vendor", "vendor_id", "vendor_details",  
            "categories", "tags", "seo",
            "name", "slug", "sku",
            "short_description", "full_description",
            "price1", "price2", "price3",
            "option1", "option2", "option3", "option4",
            "is_stock", "stock_quantity",
            "home_delivery", "pickup", "partner_delivery", "estimated_delivery_days",
            "status", "featured", "is_active",
            "images", "uploaded_images",
            "created_at", "updated_at", "is_approve",
            'specifications'
        ]
        read_only_fields = [
            "id", "vendor", "vendor_id", "slug", "status", "featured",
            "created_at", "updated_at", "is_active", "is_approve",
        ]

    def create(self, validated_data):
        categories = validated_data.pop("categories", [])
        tags = validated_data.pop("tags", [])
        uploaded_images = validated_data.pop("uploaded_images", [])
        specs_data = validated_data.pop("specifications", None)

        product = super().create(validated_data)

        if categories:
            product.categories.set(categories)
        if tags:
            product.tags.set(tags)

        if uploaded_images:
            if len(uploaded_images) > 5:
                raise serializers.ValidationError({"uploaded_images": "Maximum 5 images allowed per product."})
            for image in uploaded_images:
                ProductImage.objects.create(product=product, image=image)

        if specs_data:
            ProductSpecifications.objects.create(product=product, **specs_data)

        return product


    def update(self, instance, validated_data):
        categories = validated_data.pop("categories", None)
        tags = validated_data.pop("tags", None)
        uploaded_images = validated_data.pop("uploaded_images", [])
        specs_data = validated_data.pop("specifications", None)

        product = super().update(instance, validated_data)

        if categories is not None:
            product.categories.set(categories)
        if tags is not None:
            product.tags.set(tags)

        if uploaded_images:
            if product.images.count() + len(uploaded_images) > 5:
                raise serializers.ValidationError({"uploaded_images": "Maximum 5 images allowed per product."})
            for image in uploaded_images:
                ProductImage.objects.create(product=product, image=image)

        if specs_data:
            ProductSpecifications.objects.update_or_create(
                product=product, defaults=specs_data
            )

        return product






class VendorProductSerializer(serializers.ModelSerializer):
    prod_id = serializers.CharField(read_only=True)
    image = serializers.SerializerMethodField()
    categories = serializers.StringRelatedField(many=True, read_only=True)
    price = serializers.DecimalField(source='active_price', max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Product
        fields = [
            'prod_id',
            'name',
            'image',
            'categories',
            'price',
            'stock_quantity',
            'status',
        ]
        read_only_fields = ['prod_id', 'name', 'image', 'categories', 'price', 'stock_quantity', 'status']

    def get_image(self, obj):
        primary_img = obj.images.filter(is_primary=True).first()
        if primary_img:
            return primary_img.image.url
        return None













class ReturnProductSerializer(serializers.ModelSerializer):
    requested_by = serializers.HiddenField(default=serializers.CurrentUserDefault())
    uploaded_images = serializers.PrimaryKeyRelatedField(
        many=True,
        read_only=False,
        queryset=ImageUpload.objects.all(),
        required=False
    )
    status = serializers.CharField(read_only=True)
    order_item = serializers.PrimaryKeyRelatedField(
        queryset=OrderItem.objects.all(),
        required=False,  # Optional now
        allow_null=True
    )

    class Meta:
        model = ReturnProduct
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at", "status"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")

        if request and hasattr(request, "user"):
            user = request.user
            if getattr(user, "role", None) == UserRole.CUSTOMER.value:
                self.fields["order_item"].queryset = OrderItem.objects.filter(
                    order__customer=user,
                    status=OrderStatus.DELIVERED.value
                )

    def validate(self, data):
        user = self.context["request"].user
        order_item = data.get("order_item")

        # Only validate if order_item is provided
        if order_item:
            if order_item.order.customer != user:
                raise serializers.ValidationError("You can only return products from your own orders.")

            if order_item.status != OrderStatus.DELIVERED.value:
                raise serializers.ValidationError(
                    {"order_item": "You can only return products from delivered orders."}
                )

        # Ensure only customers can request returns
        if getattr(user, "role", None) != UserRole.CUSTOMER.value:
            raise serializers.ValidationError("Only customers can request product returns.")

        # Limit to 5 images
        images = data.get("uploaded_images", [])
        if len(images) > 5:
            raise serializers.ValidationError({"uploaded_images": "Maximum 5 images allowed."})

        return data
