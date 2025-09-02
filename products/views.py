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
from products.permissions import BasePermission, IsVendorOrAdmin
from common.models import SEO
from products.serializers import ProductSerializer, ProductSpecificationsSerializer, ProductSpecifications
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
from products.models import Promotion, Product
from products.serializers import PromotionSerializer,VendorProductSerializer
from products.models import ReturnProduct
from products.serializers import ReturnProductSerializer
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.exceptions import PermissionDenied, ValidationError
from products.enums import ReturnStatus
from notification.utils import send_notification_to_user, NotificationType
from users.models import User
from orders.serializers import OrderItemSerializer









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

        status_value = (
            ProductStatus.APPROVED.value
            if user.is_staff or getattr(user, "role", None) == UserRole.ADMIN.value
            else ProductStatus.PENDING.value
        )

        product = serializer.save(vendor=user, seo=seo_obj, status=status_value)

        # --- specifications handle ---
        specs_data = self.request.data.get("specifications")
        import json
        if specs_data:
            if isinstance(specs_data, str):
                try:
                    specs_data = json.loads(specs_data)
                except Exception:
                    specs_data = None
            if specs_data and isinstance(specs_data, dict):
                ProductSpecifications.objects.create(product=product, **specs_data)

        # --- admin notify ---
        if getattr(user, "role", None) == UserRole.VENDOR.value:
            admins = User.objects.filter(is_active=True).filter(
                models.Q(role=UserRole.ADMIN.value) | models.Q(is_staff=True)
            )
            for admin in admins:
                send_notification_to_user(
                    admin,
                    f"Vendor '{user.email}' added a new product '{product.name}'.",
                    ntype=NotificationType.PRODUCT,
                    sender=user,
                    meta_data={"action": "product_added", "product_id": product.id},
                )

    # --- new destroy override ---
    def perform_destroy(self, instance):
        if instance.orderitem_set.exists():
            raise ValidationError("This product has been ordered and cannot be deleted.")
        instance.delete()



    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def accept(self, request, pk=None):
        product = self.get_object()
        if product.status != ProductStatus.PENDING.value:
            return Response({"detail": "Only pending products can be reviewed."}, status=400)

        product.status = ProductStatus.APPROVED.value
        product.is_active = True
        product.save()

        # Notify vendor when product is accepted
        send_notification_to_user(
            product.vendor,
            f"Your product '{product.name}' has been approved by admin.",
            ntype=NotificationType.PRODUCT,
            sender=request.user,
            meta_data={"action": "product_approved", "product_id": product.id}
        )

        return Response({
            "detail": "Product approved.",
            "product": self.get_serializer(product).data
        }, status=200)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        product = self.get_object()
        if product.status == ProductStatus.REJECTED.value:
            return Response({"detail": "Product already rejected."}, status=400)

        product.status = ProductStatus.REJECTED.value
        product.is_active = False
        product.save()

        # Notify vendor when product is rejected
        send_notification_to_user(
            product.vendor,
            f"Your product '{product.name}' has been rejected by admin.",
            ntype=NotificationType.PRODUCT,
            sender=request.user,
            meta_data={"action": "product_rejected", "product_id": product.id}
        )

        # Notify vendor + admins (existing)
        # notify_product_event(product=product, action="rejected", sender=request.user)

        return Response({
            "detail": "Product rejected.",
            "product": self.get_serializer(product).data
        }, status=200)










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
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return Product.objects.none()
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

        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return Promotion.objects.none()
        
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
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return Product.objects.none()
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
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or getattr(user, "role", None) == UserRole.ADMIN.value:
            return ReturnProduct.objects.all()
        if getattr(user, "role", None) == UserRole.VENDOR.value:
            return ReturnProduct.objects.filter(product__vendor=user)
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
        instance = serializer.save(requested_by=user)
        # Send notification to vendor
        vendor = getattr(instance.product, "vendor", None)
        if vendor:
            send_notification_to_user(
                vendor,
                f"Product '{instance.product.name}' has a new return request from {user.email}.",
                ntype=NotificationType.PRODUCT,
                sender=user,
                meta_data={"action": "return_requested", "return_id": instance.id}
            )






    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        user = request.user
        return_product = self.get_object()
        is_vendor = (
            getattr(user, "role", None) == UserRole.VENDOR.value
            and getattr(return_product.product, "vendor", None) == user
        )
        is_admin = user.is_staff or getattr(user, "role", None) == UserRole.ADMIN.value
        if not (is_vendor or is_admin):
            raise PermissionDenied("You do not have permission to approve this return.")
        return_product.status = ReturnStatus.APPROVED
        return_product.save()
        # Send notification to customer
        send_notification_to_user(
            return_product.requested_by,
            f"Your return request for product '{return_product.product.name}' has been approved.",
            ntype=NotificationType.PRODUCT,
            sender=user,
            meta_data={"action": "return_approved", "return_id": return_product.id}
        )
        return Response({"detail": "Return product approved."})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        user = request.user
        return_product = self.get_object()
        is_vendor = (
            getattr(user, "role", None) == UserRole.VENDOR.value
            and getattr(return_product.product, "vendor", None) == user
        )
        is_admin = user.is_staff or getattr(user, "role", None) == UserRole.ADMIN.value
        if not (is_vendor or is_admin):
            raise PermissionDenied("You do not have permission to reject this return.")
        return_product.status = ReturnStatus.REJECTED
        return_product.save()
        # Send notification to customer
        send_notification_to_user(
            return_product.requested_by,
            f"Your return request for product '{return_product.product.name}' has been rejected.",
            ntype=NotificationType.PRODUCT,
            sender=user,
            meta_data={"action": "return_rejected", "return_id": return_product.id}
        )
        return Response({"detail": "Return product rejected."})
    





class DeliveredOrderItemViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return OrderItem.objects.none()
        return OrderItem.objects.filter(
            order__customer=user,
            status=OrderStatus.DELIVERED.value
        )
    







class BulkProductsStatusUpdateViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post"] 

    def list(self, request):
        return Response(
            {
                "detail": "Use POST /api/bulk/products/status/update-status/ "
                          "or POST /api/bulk/products/status/delete/ for bulk actions."
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="update-status")
    def bulk_update_status(self, request):
        user = request.user
        product_ids = request.data.get("product_ids", [])
        new_status = request.data.get("status")

        if getattr(user, "role", None) != UserRole.ADMIN.value:
            return Response(
                {"detail": "Only admin can update product status."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not product_ids or new_status not in ProductStatus.values:
            return Response(
                {"detail": "Invalid product IDs or status."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        products = Product.objects.filter(id__in=product_ids)
        updated_count = products.update(status=new_status)

        return Response(
            {"detail": f"Updated status of {updated_count} products to '{new_status}'."},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="delete")
    def bulk_delete(self, request):
        user = request.user
        product_ids = request.data.get("product_ids", [])

        if not product_ids:
            return Response(
                {"detail": "No product IDs provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        products = Product.objects.filter(id__in=product_ids)

        if getattr(user, "role", None) == UserRole.ADMIN.value:
            deleted_count, _ = products.delete()
            return Response(
                {"detail": f"Admin deleted {deleted_count} products."},
                status=status.HTTP_200_OK,
            )

        elif getattr(user, "role", None) == UserRole.VENDOR.value:
            vendor_products = products.filter(vendor=user)
            deleted_count, _ = vendor_products.delete()
            return Response(
                {"detail": f"Vendor deleted {deleted_count} products."},
                status=status.HTTP_200_OK,
            )

        return Response(
            {"detail": "Customers cannot perform bulk actions."},
            status=status.HTTP_403_FORBIDDEN,
        )
