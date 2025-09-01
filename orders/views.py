# orders/views.py
import logging
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, generics, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound
# from notification.utils import send_notification_to_user
from orders.models import Order, CartItem, OrderItem
from orders.serializers import (
    ShippingAddressAttachSerializer,
    ShippingAddressInlineSerializer,
    OrderSerializer,
    CartItemSerializer,
    OrderReceiptSerializer,
    ShippingAddressSerializer, 
    OrderItemSerializer
)
from orders.enums import OrderStatus, DeliveryType
from orders.utils import create_order_from_cart, create_order_for_single_product
from products.models import Product
from users.enums import UserRole
from orders.models import ShippingAddress
from rest_framework.permissions import IsAuthenticated

logger = logging.getLogger(__name__)


# -------- Permissions --------
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
from users.enums import UserRole
from orders.enums import OrderStatus


class IsVendorOrAdminOrCustomer(permissions.BasePermission):

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        role = getattr(user, "role", None)

        if role == UserRole.ADMIN.value:
            return True

        if role == UserRole.VENDOR.value:
            if view.action in ["list", "retrieve", "update", "partial_update", "destroy"]:
                return True

        if role == UserRole.CUSTOMER.value:
            if view.action in ["create_from_cart_action", "create_single_action"]:
                return request.method == "POST"
            if view.action in ["list", "retrieve"]:
                return True

        return False

    def has_object_permission(self, request, view, obj):
        role = getattr(request.user, "role", None)

        if role == UserRole.ADMIN.value:
            return True

        if role == UserRole.VENDOR.value:
            return obj.items.filter(product__vendor=request.user).exists()

        if role == UserRole.CUSTOMER.value:
            return obj.customer == request.user

        return False








class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsVendorOrAdminOrCustomer]

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, 'role', None)

        if role == UserRole.ADMIN.value or getattr(user, 'is_staff', False):
            queryset = Order.objects.all()
        elif role == UserRole.VENDOR.value:
            queryset = Order.objects.filter(items__product__vendor=user).distinct()
        elif role == UserRole.CUSTOMER.value:
            queryset = Order.objects.filter(customer=user)
        else:
            return Order.objects.none()

        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(order_date__date__range=[start_date, end_date])

        payment_status = self.request.query_params.get('payment_status')
        if payment_status:
            if payment_status.lower() == 'none':
                queryset = queryset.filter(payment_status__isnull=True)
            elif payment_status.lower() != 'all':
                queryset = queryset.filter(payment_status__iexact=payment_status)

        return queryset.order_by('-order_date')

    def perform_create(self, serializer):
        if getattr(self.request.user, "role", None) != UserRole.VENDOR.value:
            raise PermissionDenied("Only vendors can manually create orders.")
        serializer.save(vendor=self.request.user, order_status=OrderStatus.PENDING.value)


    # ---------- Cart Order ----------
    @action(detail=False, methods=["post"], url_path="create-from-cart")
    def create_from_cart_action(self, request):
        delivery_type = request.data.get("delivery_type", DeliveryType.STANDARD.value)
        if delivery_type not in [d.value for d in DeliveryType]:
            return Response({"error": "Invalid delivery type"}, status=status.HTTP_400_BAD_REQUEST)
        print("check user role:", getattr(request.user, "role", None))

        try:
            orders = create_order_from_cart(
                user=request.user,
                delivery_type=delivery_type,
                promo_code=request.data.get("promo_code"),
                discount=request.data.get("discount"),
                delivery_instruction=request.data.get("delivery_instruction"),
                estimated_delivery=request.data.get("estimated_delivery"),
                delivery_date=request.data.get("delivery_date"),
                payment_method=request.data.get("payment_method"),
                notes=request.data.get("notes"),
            )
            if not isinstance(orders, list):
                orders = [orders]

            addr_id = request.data.get("selected_shipping_address_id")
            if addr_id:
                address = get_object_or_404(ShippingAddress, id=addr_id, user=request.user)
                for order in orders:
                    order.selected_shipping_address = address
                    order.save(update_fields=["selected_shipping_address"])



            return Response(
                OrderSerializer(orders, many=True, context={"request": request}).data,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)



    @action(
        detail=False,
        methods=["post"],
        url_path="create-single",
        permission_classes=[IsAuthenticated]  
    )
    def create_single_action(self, request):
        # Validate product_id
        product_id = request.data.get("product_id")
        if not product_id:
            return Response({"error": "Product ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate quantity
        try:
            quantity = int(request.data.get("quantity", 1))
            if quantity < 1:
                return Response({"error": "Quantity must be at least 1."}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response({"error": "Quantity must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate delivery_type
        delivery_type = request.data.get("delivery_type", DeliveryType.STANDARD.value)
        if delivery_type not in [d.value for d in DeliveryType]:
            return Response({"error": "Invalid delivery type"}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch product
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)

        # Assign price explicitly
        product_price = product.price1  # <-- Use price1 here

        # Create order
        try:
            order = create_order_for_single_product(
            product=product,
            user=request.user,
            quantity=quantity,
            delivery_type=delivery_type,
            promo_code=request.data.get("promo_code"),
            discount=request.data.get("discount"),
            delivery_instruction=request.data.get("delivery_instruction"),
            estimated_delivery=request.data.get("estimated_delivery"),
            delivery_date=request.data.get("delivery_date"),
            payment_method=request.data.get("payment_method"),
            notes=request.data.get("notes"),
        )
            addr_id = request.data.get("selected_shipping_address_id")
            if addr_id:
                address = get_object_or_404(ShippingAddress, id=addr_id, user=request.user)
                order.selected_shipping_address = address
                order.save(update_fields=["selected_shipping_address"])

            # Serialize and return order
            return Response(
                OrderSerializer(order, context={"request": request}).data,
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)













class ShippingAddressViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ShippingAddressSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return ShippingAddress.objects.none()
        return ShippingAddress.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)











# -------- Cart ViewSet --------
class CartViewSet(viewsets.ModelViewSet):
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return CartItem.objects.none()
        return CartItem.objects.filter(user=self.request.user).select_related("product")

    def create(self, request, *args, **kwargs):
        from products.models import Product
        product_id = request.data.get("product_id")
        quantity = request.data.get("quantity", 1)

        if not product_id:
            return Response({"error": "product_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            quantity = int(quantity)
            if quantity < 1:
                return Response({"error": "Quantity must be at least 1."}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response({"error": "Quantity must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

        cart_item, created = CartItem.objects.update_or_create(
            user=request.user,
            product_id=product_id,
            defaults={"quantity": quantity, "price_snapshot": Product.objects.get(pk=product_id).price1},
        )
        return Response(self.get_serializer(cart_item).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def increment(self, request, pk=None):
        cart_item = self.get_object()
        if getattr(cart_item.product, "stock_quantity", None) and cart_item.quantity + 1 > cart_item.product.stock_quantity:
            return Response({"error": "Cannot exceed available stock."}, status=status.HTTP_400_BAD_REQUEST)
        cart_item.quantity += 1
        cart_item.save(update_fields=["quantity"])
        return Response(self.get_serializer(cart_item).data)

    @action(detail=True, methods=["post"])
    def decrement(self, request, pk=None):
        cart_item = self.get_object()
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save(update_fields=["quantity"])
        return Response(self.get_serializer(cart_item).data)


# -------- Order Receipt --------
class OrderReceiptView(generics.RetrieveAPIView):
    serializer_class = OrderReceiptSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, "role", None)
        if role == UserRole.ADMIN.value:
            return Order.objects.all()
        if role == UserRole.VENDOR.value:
            return Order.objects.filter(vendor=user)
        if role == UserRole.CUSTOMER.value:
            return Order.objects.filter(customer=user)
        return Order.objects.none()

    def get_object(self):
        order_id = self.kwargs.get("order_id")
        try:
            return self.get_queryset().get(order_id=order_id)
        except Order.DoesNotExist:
            raise NotFound("Receipt not found for this order.")




class OrderItemViewSet(viewsets.ModelViewSet):
    serializer_class = OrderItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        queryset = OrderItem.objects.filter(status=OrderStatus.DELIVERED.value)

        if getattr(user, "role", None) == UserRole.ADMIN.value:
            return queryset
        if getattr(user, "role", None) == UserRole.VENDOR.value:
            return queryset.filter(product__vendor=user)
        if getattr(user, "role", None) == UserRole.CUSTOMER.value:
            return queryset.filter(order__customer=user)

        return queryset.none()

    def perform_create(self, serializer):
        serializer.save()







class BulkOrderStatusUpdateView(generics.UpdateAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, "role", None)
        if role == UserRole.ADMIN.value:
            return Order.objects.all()
        if role == UserRole.VENDOR.value:
            return Order.objects.filter(vendor=user)
        if role == UserRole.CUSTOMER.value:
            return Order.objects.filter(customer=user)
        return Order.objects.none()

    def update(self, request, *args, **kwargs):
        order_ids = request.data.get("order_ids", [])
        new_status = request.data.get("order_status")

        if not order_ids or not isinstance(order_ids, list):
            return Response({"error": "order_ids must be a list of IDs."}, status=status.HTTP_400_BAD_REQUEST)

        if new_status not in [status.value for status in OrderStatus]:
            return Response({"error": "Invalid order status."}, status=status.HTTP_400_BAD_REQUEST)

        orders = self.get_queryset().filter(id__in=order_ids)
        updated_count = orders.update(order_status=new_status)

        return Response({"updated_count": updated_count}, status=status.HTTP_200_OK)