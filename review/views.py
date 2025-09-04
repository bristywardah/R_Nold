from rest_framework import viewsets, status
from rest_framework.permissions import BasePermission
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Review
from .serializers import ReviewSerializer
from users.enums import UserRole
from rest_framework import serializers

class IsCustomer(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == UserRole.CUSTOMER.value
        )


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [IsCustomer]

    def get_queryset(self):
        user = self.request.user
        if getattr(self, 'swagger_fake_view', False):
            return Review.objects.none()
        if user.is_staff or user.role == UserRole.ADMIN.value:
            return Review.objects.all()
        elif user.role == UserRole.VENDOR.value:
            return Review.objects.filter(product__vendor=user)
        else:  
            return Review.objects.filter(user=user)

    def perform_create(self, serializer):
        user = self.request.user
        product = serializer.validated_data.get("product")

        if product.vendor == user:
            raise serializers.ValidationError("You cannot review your own product.")

        if Review.objects.filter(user=user, product=product).exists():
            raise serializers.ValidationError("You have already reviewed this product.")

        serializer.save(user=user)

    @action(detail=False, methods=["get"], url_path="product/(?P<product_id>[^/.]+)/reviews")
    def product_reviews(self, request, product_id=None):
        """
        GET /api/product-reviews/product/<product_id>/reviews/
        Returns all reviews for a product.
        """
        reviews = Review.objects.filter(product_id=product_id)
        serializer = self.get_serializer(reviews, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
