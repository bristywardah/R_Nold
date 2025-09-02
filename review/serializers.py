from rest_framework import serializers
from django.utils.timesince import timesince
from django.utils import timezone
from .models import Review, ReviewImage
from users.serializers import UserSerializer
from products.models import Product


class ReviewImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewImage
        fields = ["id", "image"]


class ReviewSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source="product",
        write_only=True
    )
    product = serializers.SerializerMethodField(read_only=True)  
    time_since = serializers.SerializerMethodField()
    images = ReviewImageSerializer(many=True, read_only=True)
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(
            max_length=100000,
            allow_empty_file=False,
            use_url=False
        ),
        write_only=True,
        required=False
    )

    class Meta:
        model = Review
        fields = [
            "id", "product", "product_id", "user",
            "rating", "comment", "created_at",
            "time_since", "images", "uploaded_images"
        ]
        read_only_fields = ["id", "user", "created_at", "time_since", "images"]

    def get_product(self, obj):
        """Show limited product info instead of full ProductSerializer"""
        return {
            "id": obj.product.id,
            "name": obj.product.name,
            "slug": obj.product.slug,
        }

    def get_time_since(self, obj):
        return timesince(obj.created_at, timezone.now()) + " ago"
    

    def validate(self, attrs):
        user = self.context['request'].user
        product = attrs.get('product')
        if Review.objects.filter(user=user, product=product).exists():
            raise serializers.ValidationError("You have already reviewed this product.")
        return attrs
    
    
    def create(self, validated_data):
        uploaded_images = validated_data.pop("uploaded_images", [])
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            validated_data["user"] = request.user

        review = super().create(validated_data)

        for image in uploaded_images:
            ReviewImage.objects.create(review=review, image=image)

        return review
