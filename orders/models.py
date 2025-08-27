from decimal import Decimal
import uuid

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError

from users.models import BaseModel
from products.models import Product
from orders.enums import OrderStatus, DeliveryType, PaymentMethod

User = settings.AUTH_USER_MODEL


# -----------------------------
# Order Model
# -----------------------------
class Order(BaseModel):
    order_id = models.CharField(max_length=64, unique=True, editable=False)
    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="orders",
        limit_choices_to={"role": "customer"},
    )
    vendor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="vendor_orders",
        limit_choices_to={"role": "vendor"},
    )
    products = models.ManyToManyField(Product, through="OrderItem")
    
    selected_shipping_address = models.ForeignKey(
        "ShippingAddress", on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )

    # Monetary details
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    promo_code = models.CharField(max_length=64, blank=True, null=True)

    delivery_type = models.CharField(
        max_length=20,
        choices=DeliveryType.choices(),
        default=DeliveryType.STANDARD.value
    )

    delivery_instructions = models.TextField(blank=True, null=True)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices(),
        blank=True,
        null=True,
    )


    payment_status = models.CharField(
        max_length=20, choices=OrderStatus.choices(), default=OrderStatus.PENDING.value
    )
    order_status = models.CharField(
        max_length=20, choices=OrderStatus.choices(), default=OrderStatus.PENDING.value
    )

    estimated_delivery = models.DateTimeField(blank=True, null=True)
    item_count = models.PositiveIntegerField(default=0)

    order_date = models.DateTimeField(default=timezone.now)
    delivery_date = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["order_date"]),
            models.Index(fields=["order_status"]),
            models.Index(fields=["payment_status"]),
        ]

    def __str__(self):
        name_method = getattr(self.customer, "get_full_name", None)
        customer_name = name_method() if callable(name_method) else getattr(self.customer, "email", str(self.customer))
        return f"Order {self.order_id} - {customer_name}"

    def save(self, *args, **kwargs):
        if not self.order_id:
            self.order_id = f"ORD{timezone.now().strftime('%Y%m%d')}{str(uuid.uuid4()).split('-')[0].upper()}"
        super().save(*args, **kwargs)

    def update_totals(self, tax_rate: Decimal | float | None = None, delivery_fee_override: Decimal | None = None):
        subtotal = sum((item.price or Decimal("0.00")) * item.quantity for item in self.items.all())
        item_count = sum(item.quantity for item in self.items.all())

        discount = self.discount_amount or Decimal("0.00")

        if tax_rate is None:
            tax_rate = Decimal(getattr(settings, "DEFAULT_TAX_RATE", 0))  # e.g., 0.05 for 5%

        if delivery_fee_override is not None:
            delivery_fee = Decimal(delivery_fee_override)
        else:
            fees_map = getattr(
                settings, "DELIVERY_FEES",
                {"standard": Decimal("0.00"), "express": Decimal("0.00"), "pickup": Decimal("0.00")}
            )
            delivery_fee = Decimal(fees_map.get(self.delivery_type, 0))

        taxable_amount = max(subtotal - discount, Decimal("0.00"))
        tax_amount = (Decimal(tax_rate) * taxable_amount).quantize(Decimal("0.01"))

        total = (taxable_amount + tax_amount + delivery_fee).quantize(Decimal("0.01"))

        self.subtotal = subtotal.quantize(Decimal("0.01"))
        self.tax_amount = tax_amount
        self.delivery_fee = delivery_fee
        self.total_amount = total
        self.item_count = item_count
        self.save(update_fields=["subtotal", "tax_amount", "delivery_fee", "total_amount", "item_count"])
        return self


# -----------------------------
# Order Item
# -----------------------------
class OrderItem(BaseModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices(),
        default=OrderStatus.PENDING.value
    )

    def __str__(self):
        return f"{self.quantity} x {self.product.name} for {self.order.order_id}"



# -----------------------------
# Cart Item
# -----------------------------
# models.py
class CartItem(BaseModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="cart_items")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cart_items")
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    price_snapshot = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    saved_for_later = models.BooleanField(default=False)

    class Meta:
        unique_together = ("product", "user")
        ordering = ["-updated_at"]

    def subtotal(self):
        return (self.price_snapshot or Decimal("0.00")) * Decimal(self.quantity)

    def clean(self):
        if getattr(self.product, "is_stock", False) and getattr(self.product, "stock_quantity", None) is not None:
            if self.quantity > self.product.stock_quantity:
                raise ValidationError({"quantity": "Requested quantity exceeds available stock."})



# -----------------------------
# Shipping Address
# -----------------------------
class ShippingAddress(BaseModel):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="shipping_addresses")
    order = models.ForeignKey(Order, related_name="shipping_addresses", null=True, blank=True, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=30)
    email = models.EmailField(blank=True, null=True)
    street_address = models.TextField()
    landmark = models.CharField(max_length=255, blank=True, null=True)
    apartment_name = models.CharField(max_length=255, blank=True, null=True)
    floor_number = models.CharField(max_length=32, blank=True, null=True)
    flat_number = models.CharField(max_length=32, blank=True, null=True)
    city = models.CharField(max_length=128)
    zip_code = models.CharField(max_length=32)
    billing_same_as_shipping = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.full_name} - {self.city}"
