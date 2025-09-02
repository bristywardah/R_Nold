
from rest_framework import serializers
from common.models import Category, Tag, SEO, SavedProduct
from products.models import Product
from users.serializers import UserPublicSerializer
from orders.models import Order, OrderItem, ShippingAddress
from common.models import ImageUpload
from common.models import Banner, Wishlist
from products.serializers import ProductSerializer

class ImageUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImageUpload
        fields = ["id", "image", "alt_text", "uploaded_at"]



# -------------------
# Category
# -------------------
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'image', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']

    def validate_name(self, value):
        qs = Category.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Category with this name already exists.")
        return value





# -------------------
# Tag
# -------------------
class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug', 'created_at', 'updated_at']
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']

    def validate_name(self, value):
        qs = Tag.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Tag with this name already exists.")
        return value


# -------------------
# SEO
# -------------------
class SEOSerializer(serializers.ModelSerializer):
    class Meta:
        model = SEO
        fields = ['id', 'title', 'meta_description']


# -------------------
# SavedProduct
# -------------------
class SavedProductSerializer(serializers.ModelSerializer):
    vendor = UserPublicSerializer(read_only=True)

    class Meta:
        model = SavedProduct
        fields = [
            'id', 'vendor', 'name', 'data', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'vendor', 'created_at', 'updated_at']
        ref_name = "SavedProductsSerializer"


    def create(self, validated_data):
        validated_data['vendor'] = self.context['request'].user
        return super().create(validated_data)




class OrderListSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    vendor_name = serializers.SerializerMethodField()
    total = serializers.DecimalField(source='total_amount', max_digits=10, decimal_places=2, read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    order_status_display = serializers.CharField(source='get_order_status_display', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'order_id',
            'order_date',
            'total',
            'payment_method_display',
            'order_status_display',
            'customer_name',
            'vendor_name',
        ]

    def get_customer_name(self, obj):
        user = obj.customer
        if user:
            full_name = getattr(user, 'get_full_name', None)
            if callable(full_name):
                name = full_name()
                if name:
                    return name
            name = (user.first_name + " " + user.last_name).strip()
            if name:
                return name
            return getattr(user, 'email', 'Unknown Customer')
        return None

    def get_vendor_name(self, obj):
        user = obj.vendor
        if user:
            full_name = getattr(user, 'get_full_name', None)
            if callable(full_name):
                name = full_name()
                if name:
                    return name
            name = (user.first_name + " " + user.last_name).strip()
            if name:
                return name
            return getattr(user, 'email', 'Unknown Vendor')
        return None



class BannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = [
            'id', 'is_active', 'image', 'title', 'subtitle', 
            'position', 'alt_text', 'link', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        ref_name = "BannerSerializer"


    def validate_image(self, value):
        if not value:
            raise serializers.ValidationError("Image is required.")
        return value







class WishlistSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )

    class Meta:
        model = Wishlist
        fields = ['id', 'user', 'product', 'product_id', 'added_at']
        read_only_fields = ['id', 'user', 'product', 'added_at']
        ref_name = "WishlistSerializer"

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)