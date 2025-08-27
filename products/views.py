from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from .models import Product, ProductImage
from .serializers import ProductSerializer, ProductImageSerializer
from products.enums import ProductStatus
from products.permissions import BasePermission
from common.models import SEO
from products.serializers import ProductSerializer
from django.db.models import Sum
from products.models import Product
from django.db.models import Sum, F
from django.db.models import Case, When, IntegerField
from rest_framework.permissions import BasePermission
from rest_framework import filters
from rest_framework.pagination import PageNumberPagination
from django.db.models import Sum, Case, When, DecimalField
from users.enums import UserRole
from orders.models import OrderItem, OrderStatus, Order
from django.db.models.functions import Coalesce
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum
from django.db import models
from django.db.models import OuterRef, Subquery
from products.models import Promotion
from products.serializers import PromotionSerializer,VendorProductSerializer
from products.models import ReturnProduct
from products.serializers import ReturnProductSerializer
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
# from notification.utils import send_notification_to_user
from rest_framework.exceptions import PermissionDenied, ValidationError


class IsVendorOrAdmin(BasePermission):

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and (
            request.user.is_staff or getattr(request.user, "role", None) == "vendor"
        )

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return (
            request.user.is_staff or
            (getattr(request.user, "role", None) == "vendor" and obj.vendor == request.user)
        )
    










class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsVendorOrAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = Product.objects.select_related("seo", "vendor").prefetch_related(
            "categories", "tags", "images"
        )
        user = self.request.user

        if user.is_authenticated:
            if user.is_staff or user.is_superuser:
                return qs
            if getattr(user, "role", None) == UserRole.VENDOR.value:
                return qs.filter(vendor=user)

        return qs.filter(is_active=True, status=ProductStatus.APPROVED.value)

    def perform_create(self, serializer):
        user = self.request.user
        if not (user.is_staff or getattr(user, "role", None) in [UserRole.ADMIN.value, UserRole.VENDOR.value]):
            raise PermissionDenied("Only vendors or admins can add products.")

        seo_data = self.request.data.get("seo")
        seo_obj = None

        if isinstance(seo_data, dict):
            seo_obj = SEO.objects.create(**seo_data)
        elif seo_data:
            try:
                seo_obj = SEO.objects.get(pk=seo_data)
            except SEO.DoesNotExist:
                raise ValidationError({"seo": "SEO object not found."})

        status_value = ProductStatus.APPROVED if user.is_staff or getattr(user, "role", None) == UserRole.ADMIN.value else ProductStatus.PENDING
        serializer.save(vendor=user, seo=seo_obj, status=status_value)

    # ---------- Approve ----------
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def accept(self, request, pk=None):
        product = self.get_object()
        if product.status != ProductStatus.PENDING.value:
            return Response({"detail": "Only pending products can be reviewed."}, status=status.HTTP_400_BAD_REQUEST)

        product.status = ProductStatus.APPROVED.value
        product.is_active = True
        product.save()

        # Optional notification
        # if product.vendor:
        #     send_notification_to_user(user=product.vendor, message=f"Your product '{product.name}' has been approved!", sender=request.user, meta_data={"product_id": product.id, "status": "approved"})

        return Response({
            "detail": "Product approved.",
            "product": self.get_serializer(product).data
        }, status=status.HTTP_200_OK)

    # ---------- Reject ----------
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        product = self.get_object()
        if product.status == ProductStatus.REJECTED.value:
            return Response({"detail": "Product already rejected."}, status=status.HTTP_400_BAD_REQUEST)

        product.status = ProductStatus.REJECTED.value
        product.is_active = False
        product.save()

        # if product.vendor:
        #     send_notification_to_user(
        #         user=product.vendor,
        #         message=f"Your product '{product.name}' has been rejected",
        #         sender=request.user,
        #         meta_data={"product_id": product.id, "status": "rejected"}
        #     )

        return Response({
            "detail": "Product rejected.",
            "product": self.get_serializer(product).data
        }, status=status.HTTP_200_OK)

    # ---------- Soft-delete if part of orders ----------
    def destroy(self, request, *args, **kwargs):
        product = self.get_object()

        if OrderItem.objects.filter(product=product).exists():
            product.is_active = False
            product.save()
            return Response(
                {"detail": "Product cannot be deleted because it is part of existing orders. It has been deactivated instead."},
                status=status.HTTP_200_OK
            )

        return super().destroy(request, *args, **kwargs)















class ProductImageViewSet(viewsets.ModelViewSet):
    serializer_class = ProductImageSerializer
    permission_classes = [permissions.IsAuthenticated, IsVendorOrAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        qs = ProductImage.objects.select_related("product")
        product_id = self.kwargs.get("product_pk")
        if product_id:
            qs = qs.filter(product_id=product_id)
        return qs

    def create(self, request, *args, **kwargs):
        product_id = self.kwargs.get("product_pk")
        product = get_object_or_404(Product, pk=product_id)

        if not (
            request.user.is_staff
            or (
                getattr(request.user, "role", None) == UserRole.VENDOR.value
                and product.vendor == request.user
            )
        ):
            raise PermissionDenied("You do not have permission to add images to this product.")

        images = request.FILES.getlist("images")
        if not images:
            return Response({"detail": "No images uploaded."}, status=status.HTTP_400_BAD_REQUEST)

        if product.images.count() + len(images) > 5:
            return Response({"detail": "You can upload maximum 5 images per product."},
                            status=status.HTTP_400_BAD_REQUEST)

        created_images = []
        for image in images:
            img_obj = ProductImage.objects.create(product=product, image=image)
            created_images.append(img_obj)

        serializer = self.get_serializer(created_images, many=True, context={"product": product})
        return Response(
            {"detail": "Images uploaded successfully.", "images": serializer.data},
            status=status.HTTP_201_CREATED,
        )





class IsVendorOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.role == UserRole.VENDOR.value or
            request.user.role == UserRole.ADMIN.value
        )


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10  
    page_size_query_param = 'page_size'
    max_page_size = 100









class TopSellProductViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsVendorOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'is_active', 'vendor']
    search_fields = ['name', 'sku', 'categories__name', 'tags__name']
    ordering_fields = [
        'price1', 'price2', 'price3',
        'total_quantity_sold', 'total_discount', 'created_at'
    ]
    ordering = ['-total_quantity_sold']
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user

        delivered_items = OrderItem.objects.filter(
            order__order_status=OrderStatus.DELIVERED.value
        )

        if user.role == UserRole.VENDOR.value:
            delivered_items = delivered_items.filter(product__vendor=user)

        top_products = delivered_items.values('product').annotate(
            total_quantity_sold=Sum('quantity')
        ).order_by('-total_quantity_sold')

        product_ids = [item['product'] for item in top_products]

        products_qs = Product.objects.filter(id__in=product_ids)

        preserved_order = Case(
            *[When(pk=pk, then=pos) for pos, pk in enumerate(product_ids)]
        )

        subquery = OrderItem.objects.filter(
            order__order_status=OrderStatus.DELIVERED.value,
            product=OuterRef('pk')
        ).values('product').annotate(
            total_qty=Sum('quantity')
        ).values('total_qty')

        products = products_qs.annotate(
            total_quantity_sold=Subquery(subquery, output_field=IntegerField())
        ).order_by(preserved_order)

        return products

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)










class PromotionViewSet(viewsets.ModelViewSet):
    serializer_class = PromotionSerializer
    queryset = Promotion.objects.all()

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['discount_type', 'is_active', 'products']
    search_fields = ['name', 'description']
    ordering_fields = ['start_datetime', 'end_datetime', 'discount_value']
    ordering = ['-start_datetime']

    def get_queryset(self):
        user = self.request.user

        if user.role == UserRole.ADMIN.value:
            return Promotion.objects.all()

        elif user.role == UserRole.VENDOR.value:
            return Promotion.objects.filter(products__vendor=user).distinct()

        else:
            raise PermissionDenied("You do not have permission to access promotions.")

    def perform_create(self, serializer):
        user = self.request.user

        if user.role not in [UserRole.ADMIN.value, UserRole.VENDOR.value]:
            raise PermissionDenied("Only vendors or admins can create promotions.")

        products = serializer.validated_data.get("products", [])
        if user.role == UserRole.VENDOR.value:
            for product in products:
                if product.vendor != user:
                    raise PermissionDenied("You can only create promotions for your own products.")

        serializer.save()

    def perform_update(self, serializer):
        user = self.request.user

        if user.role not in [UserRole.ADMIN.value, UserRole.VENDOR.value]:
            raise PermissionDenied("Only vendors or admins can update promotions.")

        products = serializer.validated_data.get("products", [])
        if user.role == UserRole.VENDOR.value:
            for product in products:
                if product.vendor != user:
                    raise PermissionDenied("You can only update promotions for your own products.")

        serializer.save()




class VendorProductList(viewsets.ModelViewSet):
    serializer_class = VendorProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsVendorOrAdmin]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['name']
    filterset_fields = ['categories', 'status']  
    ordering_fields = ['status']

    def get_queryset(self):
        user = self.request.user
        base_qs = Product.objects.select_related("seo").prefetch_related("categories", "tags", "images")

        if user.role == UserRole.VENDOR.value:
            return base_qs.filter(vendor=user)
        elif user.role == UserRole.ADMIN.value:
            return base_qs
        else:
            raise PermissionDenied("You do not have permission to view vendor products.")

    def perform_update(self, serializer):
        product = self.get_object()
        user = self.request.user

        if user.role == UserRole.ADMIN.value or (user.role == UserRole.VENDOR.value and product.vendor == user):
            serializer.save()
        else:
            raise PermissionDenied("You do not have permission to update this product.")

    def perform_destroy(self, instance):
        user = self.request.user

        if user.role == UserRole.ADMIN.value or (user.role == UserRole.VENDOR.value and instance.vendor == user):
            instance.delete()
        else:
            raise PermissionDenied("You do not have permission to delete this product.")













class ReturnProductViewSet(viewsets.ModelViewSet):
    queryset = ReturnProduct.objects.all()
    serializer_class = ReturnProductSerializer

    def get_queryset(self):
        user = self.request.user

        if user.is_staff or getattr(user, "role", None) == UserRole.ADMIN.value:
            return ReturnProduct.objects.all()

        if getattr(user, "role", None) == UserRole.VENDOR.value:
            return ReturnProduct.objects.filter(order_item__product__vendor=user)

        if getattr(user, "role", None) == UserRole.CUSTOMER.value:
            return ReturnProduct.objects.filter(requested_by=user)

        return ReturnProduct.objects.none()

    def perform_create(self, serializer):
        user = self.request.user

        if getattr(user, "role", None) != UserRole.CUSTOMER.value:
            raise PermissionDenied("Only customers can request returns.")

        order_item = serializer.validated_data.get("order_item")

        if order_item:
            if order_item.order.customer != user:
                raise PermissionDenied("You can only return products from your own orders.")
            if order_item.status != OrderStatus.DELIVERED.value:
                raise serializers.ValidationError(
                    {"order_item": "You can only return products from delivered orders."}
                )

        serializer.save(requested_by=user)









