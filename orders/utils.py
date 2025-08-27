# orders/utils.py
import logging
from decimal import Decimal
from django.db import transaction
from orders.models import Order, OrderItem, CartItem
from orders.enums import OrderStatus, DeliveryType

logger = logging.getLogger(__name__)

def _to_decimal(val, default="0.00"):
    if val in (None, "", 0):
        return Decimal(default)
    try:
        return Decimal(str(val))
    except Exception:
        return Decimal(default)

def create_order_from_cart(
    user,
    delivery_type=DeliveryType.STANDARD.value,
    promo_code=None,
    discount=None,
    delivery_instruction=None,
    estimated_delivery=None,
    delivery_date=None,
    payment_method=None,
    notes=None,
):
    """
    Create an order from user's cart.
    NOTE: No ShippingAddress is created here. It can be added later via API.
    """
    cart_qs = (
        CartItem.objects
        .filter(user=user, saved_for_later=False)
        .select_related("product", "product__vendor")
    )
    if not cart_qs.exists():
        raise ValueError("Cart is empty")

    # Assuming single-vendor cart; otherwise you should split per-vendor
    vendor = {ci.product.vendor for ci in cart_qs}.pop()

    with transaction.atomic():
        order = Order.objects.create(
            customer=user,
            vendor=vendor,
            delivery_type=delivery_type,
            promo_code=promo_code,
            discount_amount=_to_decimal(discount),
            delivery_instructions=delivery_instruction or "",
            estimated_delivery=estimated_delivery,  # can be date/datetime per model
            delivery_date=delivery_date,
            payment_method=payment_method or "",
            notes=notes or "",
            subtotal=Decimal("0.00"),
            total_amount=Decimal("0.00"),
            order_status=OrderStatus.PENDING.value,
            payment_status=OrderStatus.PENDING.value,
        )

        # Add items
        for ci in cart_qs:
            OrderItem.objects.create(
                order=order,
                product=ci.product,
                quantity=ci.quantity,
                price=ci.price_snapshot,
            )

        # Compute totals (your model should implement this)
        order.update_totals()

        # Clear cart
        cart_qs.delete()

    logger.info(f"Order {order.order_id} created from cart for user {user.id}")
    return order


def create_order_for_single_product(
    product, user, quantity=1,
    delivery_type=DeliveryType.STANDARD.value,
    promo_code=None,
    discount=None,
    delivery_instruction=None,
    estimated_delivery=None,
    delivery_date=None,
    payment_method=None,
    notes=None,
):
    """
    Create an order for a single product (no shipping created here).
    """
    with transaction.atomic():
        order = Order.objects.create(
            customer=user,
            vendor=product.vendor,
            delivery_type=delivery_type,
            promo_code=promo_code,
            discount_amount=_to_decimal(discount),
            delivery_instructions=delivery_instruction or "",
            estimated_delivery=estimated_delivery,
            delivery_date=delivery_date,
            payment_method=payment_method or "",
            notes=notes or "",
            order_status=OrderStatus.PENDING.value,
            payment_status=OrderStatus.PENDING.value,
        )

        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            price=getattr(product, "price1", product.price),
        )

        order.update_totals()

    logger.info(f"Order {order.order_id} created for single product {product.id} by user {user.id}")
    return order
