# common/views.py
from rest_framework import viewsets, permissions, filters, status
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError


from common.models import Category, Tag, SEO, SavedProduct
from common.serializers import (
    CategorySerializer, TagSerializer, SEOSerializer,
    SavedProductSerializer
)

from orders.models import Order

from common.serializers import OrderListSerializer
from rest_framework.permissions import BasePermission
from users.enums import UserRole
from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.pagination import PageNumberPagination
import logging
from common.models import Banner, Wishlist
from common.serializers import BannerSerializer, WishlistSerializer
from common.permissions import IsAdminOrReadOnly


logger = logging.getLogger(__name__)


class IsVendor(BasePermission):
    def has_permission(self, request, view):
        return getattr(request.user, "role", None) == UserRole.VENDOR.value



# -------------------
# Permissions
# -------------------
class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)


class IsVendorOrAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        user = request.user
        return user and user.is_authenticated and (user.is_staff or getattr(user, "role", None) == "vendor")


class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return getattr(obj, 'vendor', None) == request.user or getattr(obj, 'user', None) == request.user


# -------------------
# Category
# -------------------

from django.utils.text import slugify
import uuid

class IsAdminOrVendor(permissions.BasePermission):

    def has_permission(self, request, view):
        # Read-only actions are allowed for everyone
        if view.action in ['list', 'retrieve']:
            return True
        # Only staff/admin or vendor can create/update/delete
        user = request.user
        return user.is_authenticated and (user.is_staff or getattr(user, 'role', None) in ['vendor', 'admin'])


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrVendor]  
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['name']

    def perform_create(self, serializer):
        if not serializer.validated_data.get('slug'):
            name = serializer.validated_data.get('name')
            base_slug = slugify(name) or str(uuid.uuid4())[:8]
            slug = base_slug
            i = 1
            while Category.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{i}"
                i += 1
            serializer.save(slug=slug)
        else:
            serializer.save()


# -------------------
# Tag
# -------------------
class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [IsVendorOrAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['name']

    def create(self, request, *args, **kwargs):
        """
        If tag with same name exists (case-insensitive), reuse it.
        Else create new.
        """
        name = (request.data.get('name') or "").strip()
        if not name:
            raise DRFValidationError({"name": "This field is required."})

        tag = Tag.objects.filter(name__iexact=name).first()
        if tag:
            serializer = self.get_serializer(tag)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = self.get_serializer(data={"name": name})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# -------------------
# SEO
# -------------------
class SEOViewSet(viewsets.ModelViewSet):
    queryset = SEO.objects.all()
    serializer_class = SEOSerializer
    permission_classes = [IsVendorOrAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'meta_description']
    ordering_fields = ['id']

    def create(self, request, *args, **kwargs):

        title = (request.data.get('title') or "").strip()
        if not title:
            raise DRFValidationError({"title": "This field is required."})

        seo = SEO.objects.filter(title__iexact=title).first()
        if seo:
            serializer = self.get_serializer(seo)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)



class SavedProductViewSet(viewsets.ModelViewSet):
    serializer_class = SavedProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return SavedProduct.objects.none()
        return SavedProduct.objects.filter(vendor=self.request.user)

    def perform_create(self, serializer):
        if getattr(self.request.user, "role", None) != "vendor":
            raise PermissionDenied("Only vendors can save products.")
        serializer.save(vendor=self.request.user)

    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)





class StandardResultsSetPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 100



class OrderManagementViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderListSerializer
    pagination_class = StandardResultsSetPagination

    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = [
        'order_id',
        'customer__first_name',
        'customer__last_name',
        'vendor__first_name',
        'vendor__last_name'
    ]
    filterset_fields = ['payment_status', 'order_status']

    def get_queryset(self):
        user = self.request.user
        if getattr(self, 'swagger_fake_view', False) or not user.is_authenticated:
            return Order.objects.none()

        print("role", getattr(user, "role", None))

        # Admin sees all orders
        if getattr(user, 'role', None) == UserRole.ADMIN.value or getattr(user, 'is_staff', False):
            queryset = Order.objects.all()
        # Vendor sees only orders containing their products
        elif getattr(user, 'role', None) == UserRole.VENDOR.value:
            queryset = Order.objects.filter(items__product__vendor=user).distinct()
        # Customer sees only their own orders
        elif getattr(user, 'role', None) == UserRole.CUSTOMER.value:
            queryset = Order.objects.filter(customer=user)
        else:
            return Order.objects.none()

        # Date range filter
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(order_date__date__range=[start_date, end_date])

        # Payment status filter
        payment_status = self.request.query_params.get('payment_status')
        if payment_status:
            if payment_status.lower() == 'none':
                queryset = queryset.filter(payment_status__isnull=True)
            elif payment_status.lower() != 'all':
                queryset = queryset.filter(payment_status__iexact=payment_status)

        return queryset.order_by('-order_date')




# views.py
class BannerViewSet(viewsets.ModelViewSet):
    queryset = Banner.objects.all()
    serializer_class = BannerSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'subtitle', 'alt_text', 'description']
    ordering_fields = ['created_at', 'updated_at', 'position']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        is_active = self.request.query_params.get('is_active')

        if is_active is not None:
            # Convert string to bool safely
            if is_active.lower() in ["true", "1", "yes"]:
                queryset = queryset.filter(is_active=True)
            elif is_active.lower() in ["false", "0", "no"]:
                queryset = queryset.filter(is_active=False)

        return queryset

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()





class WishlistViewSet(viewsets.ModelViewSet):
    serializer_class = WishlistSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return Wishlist.objects.none()
        return Wishlist.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        if getattr(self.request.user, "role", None) != "customer":
            raise PermissionDenied("Only customers can add to wishlist.")
        serializer.save(user=self.request.user)