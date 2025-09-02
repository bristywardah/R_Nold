from rest_framework import serializers
from products.models import Product, ProductImage, Promotion, ReturnProduct, ProductSpecifications
from common.models import Category, Tag, SEO, ImageUpload
from products.enums import DiscountType
from django.db.models import Q
from users.enums import UserRole
from orders.models import OrderItem
from orders.enums import OrderStatus
from review.models import Review



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



class ProductReviewInlineSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ["id", "rating", "comment", "user", "created_at"]

    def get_user(self, obj):
        first_name = getattr(obj.user, "first_name", "")
        last_name = getattr(obj.user, "last_name", "")
        full_name = (first_name + " " + last_name).strip()
        if full_name:
            name = full_name
        else:
            name = getattr(obj.user, "username", "Unknown")
        return {
            "id": obj.user.id,
            "name": name
        }







class ProductSerializer(serializers.ModelSerializer):
    prod_id = serializers.CharField(read_only=True)
    vendor = serializers.HiddenField(default=serializers.CurrentUserDefault())
    vendor_id = serializers.IntegerField(source="vendor.id", read_only=True)
    vendor_details = serializers.SerializerMethodField()
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
    reviews = ProductReviewInlineSerializer(many=True, read_only=True)
    
    average_rating = serializers.SerializerMethodField()

    specifications = serializers.SerializerMethodField()

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
            "specifications", "average_rating", "reviews", 
        ]
        read_only_fields = [
            "id", "average_rating", "vendor", "vendor_id", "slug", "status", "featured",
            "created_at", "updated_at", "is_active", "is_approve",
        ]
        ref_name = "ProductsProductSerializer"


    def get_average_rating(self, obj):
        reviews = obj.reviews.all()
        if not reviews.exists():
            return 0
        total = sum([r.rating for r in reviews])
        return round(total / reviews.count(), 2)  


    def get_vendor_details(self, obj):
        from users.serializers import UserSerializer
        return UserSerializer(obj.vendor).data

    def get_specifications(self, obj):
        try:
            specs = ProductSpecifications.objects.get(product=obj)
            return ProductSpecificationsSerializer(specs).data
        except ProductSpecifications.DoesNotExist:
            return None
        
    def create(self, validated_data):
        categories = validated_data.pop("categories", [])
        tags = validated_data.pop("tags", [])
        uploaded_images = validated_data.pop("uploaded_images", [])
        specs_data = validated_data.pop("specifications", None)
        print("specs_data:", specs_data, type(specs_data))  # Debug line


        # If frontend sends JSON string, parse it
        import json
        if isinstance(specs_data, str):
            try:
                specs_data = json.loads(specs_data)
            except Exception:
                specs_data = None

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

        if specs_data and isinstance(specs_data, dict):
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
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(),
        required=False,
        write_only=True
    )
    uploaded_images_list = serializers.SerializerMethodField(read_only=True)

    status = serializers.CharField(read_only=True)
    order_item = serializers.PrimaryKeyRelatedField(
        queryset=OrderItem.objects.all(),
        required=True,
    )
    description = serializers.CharField(required=True)
    vendor_details = serializers.SerializerMethodField()

    class Meta:
        model = ReturnProduct
        fields = [
            "id", "order_item", "uploaded_images", "uploaded_images_list", "description", "requested_by", "status",
            "created_at", "updated_at", "vendor_details"
        ]
        read_only_fields = ["id", "created_at", "updated_at", "status", "requested_by", "vendor_details"]

    def get_vendor_details(self, obj):
        vendor = getattr(obj.product, "vendor", None)
        if vendor:
            return {
                "id": vendor.id,
                "email": getattr(vendor, "email", ""),
                "first_name": getattr(vendor, "first_name", ""),
                "last_name": getattr(vendor, "last_name", ""),
                "role": getattr(vendor, "role", ""),
            }
        return None

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

    def create(self, validated_data):
        order_item = validated_data.get("order_item")
        if order_item:
            validated_data["product"] = order_item.product
        uploaded_images = validated_data.pop("uploaded_images", [])
        instance = super().create(validated_data)

        for image_file in uploaded_images:
            img_obj = ImageUpload.objects.create(image=image_file, uploaded_by=instance.requested_by)
            instance.uploaded_images.add(img_obj)
        return instance
    


    def get_uploaded_images_list(self, obj):
        return [
            {
                "id": img.id,
                "image": img.image.url,
                "alt_text": img.alt_text,
                "uploaded_at": img.uploaded_at
            }
            for img in obj.uploaded_images.all()
        ]

    def validate(self, data):
        user = self.context["request"].user
        order_item = data.get("order_item")

        if order_item:
            if order_item.order.customer != user:
                raise serializers.ValidationError("You can only return products from your own orders.")
            if order_item.status != OrderStatus.DELIVERED.value:
                raise serializers.ValidationError(
                    {"order_item": "You can only return products from delivered orders."}
                )

        if getattr(user, "role", None) != UserRole.CUSTOMER.value:
            raise serializers.ValidationError("Only customers can request product returns.")

        images = data.get("uploaded_images", [])
        if len(images) > 5:
            raise serializers.ValidationError({"uploaded_images": "Maximum 5 images allowed."})

        return data