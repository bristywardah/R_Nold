from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.urls import reverse
from django.conf import settings
from decimal import Decimal
import uuid
from users.models import BaseModel
from products.enums import ProductStatus, DiscountType, ReturnStatus
from django.db.models import Avg
from django.utils import timezone



User = settings.AUTH_USER_MODEL






class Product(BaseModel):
    vendor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="products",
        limit_choices_to={"role": "vendor"},
    )

    categories = models.ManyToManyField("common.Category", related_name="products", blank=True)
    tags = models.ManyToManyField("common.Tag", related_name="products", blank=True)
    seo = models.ForeignKey("common.SEO", on_delete=models.SET_NULL, null=True, blank=True)

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    sku = models.CharField(max_length=64, blank=True, null=True, help_text="Optional SKU for inventory")

    short_description = models.CharField(max_length=500, blank=True)
    full_description = models.TextField(blank=True)

    price1 = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    price2 = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(Decimal('0.00'))])
    price3 = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(Decimal('0.00'))])

    option1 = models.CharField(max_length=100, blank=True)
    option2 = models.CharField(max_length=100, blank=True)
    option3 = models.CharField(max_length=100, blank=True)
    option4 = models.CharField(max_length=100, blank=True)

    is_stock = models.BooleanField(default=True)
    stock_quantity = models.PositiveIntegerField(default=0)

    home_delivery = models.BooleanField(default=False)
    pickup = models.BooleanField(default=False)
    partner_delivery = models.BooleanField(default=False)
    estimated_delivery_days = models.PositiveIntegerField(blank=True, null=True)

    status = models.CharField(
        max_length=30,
        choices=ProductStatus.choices,
        default=ProductStatus.DRAFT
    )
    featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, help_text="General availability toggle")
    is_approve = models.BooleanField(default=False)



    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["vendor"]),
            models.Index(fields=["status", "is_active"]),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.price1 is None:
            raise ValidationError({"price1": "Primary price must be set."})
        if any(p is not None and p < Decimal('0.00') for p in [self.price1, self.price2, self.price3]):
            raise ValidationError("Prices must be non-negative.")

        if self.is_stock and (self.stock_quantity is None or self.stock_quantity < 0):
            raise ValidationError({"stock_quantity": "Stock quantity must be >= 0."})

        if (self.home_delivery or self.partner_delivery or self.pickup) and self.estimated_delivery_days is None:
            raise ValidationError({"estimated_delivery_days": "Set estimated_delivery_days when product supports delivery/pickup."})

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or str(uuid.uuid4())[:8]
            slug = base
            i = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def active_price(self):
        for price in (self.price1, self.price2, self.price3):
            if price is not None:
                return price
        return Decimal('0.00')

    @property
    def average_rating(self):
        agg = self.reviews.aggregate(avg=Avg('rating'))
        return agg['avg'] or 0

    @property
    def available_stock(self):
        return None if not self.is_stock else self.stock_quantity
    
    @property
    def prod_id(self):
        return f"PROD-{1000 + self.id}"

    def get_absolute_url(self):
        try:
            return reverse("products:detail", args=[self.slug])
        except Exception:
            return f"/products/{self.slug}/"




class ProductImage(BaseModel):
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/%Y/%m/%d/")
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False, help_text="Primary image used as thumbnail")

    class Meta:
        ordering = ["-is_primary", "-created_at"]
        indexes = [models.Index(fields=["product"])]

    def __str__(self):
        return f"Image for {self.product.name}"

    def save(self, *args, **kwargs):
        if self.is_primary:
            ProductImage.objects.filter(product=self.product, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class Promotion(BaseModel):
    name = models.CharField(max_length=255)
    discount_type = models.CharField(
        max_length=20,
        choices=DiscountType.choices,  
        default=DiscountType.PERCENTAGE,
    )
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Enter percentage (0-100) for percentage discount or amount for flat discount."
    )
    products = models.ManyToManyField(
        "products.Product",
        related_name="promotions",
        help_text="Select products this promotion applies to."
    )
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-start_datetime"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["discount_type"]),
            models.Index(fields=["start_datetime", "end_datetime"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_discount_type_display()} - {self.discount_value})"

    def clean(self):
        if self.discount_type == DiscountType.PERCENTAGE:
            if self.discount_value < 0 or self.discount_value > 100:
                raise ValidationError("Percentage discount must be between 0 and 100.")

        if self.end_datetime <= self.start_datetime:
            raise ValidationError("End date must be after start date.")

    def calculate_discounted_price(self, product_price: Decimal) -> Decimal:
        if self.discount_type == DiscountType.PERCENTAGE:
            discount_amount = (product_price * self.discount_value) / 100
        else:  
            discount_amount = self.discount_value
        return max(product_price - discount_amount, Decimal('0.00'))

    @property
    def status(self):
        now = timezone.now()
        if self.start_datetime > now:
            return "Scheduled"
        elif self.end_datetime < now:
            return "Expired"
        else:
            return "Active"
        


# models.py
class ProductSpecifications(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="specifications")

    dimensions = models.CharField(max_length=255, null=True, blank=True)
    material = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=100, null=True, blank=True)
    weight = models.CharField(max_length=100, null=True, blank=True)
    assembly_required = models.BooleanField(default=False)
    warranty = models.CharField(max_length=255, null=True, blank=True)
    care_instructions = models.TextField(null=True, blank=True)
    country_of_origin = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"Specs of {self.product.name}"




class ReturnProduct(BaseModel):
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="return_requests"
    )
    order_item = models.ForeignKey(
        "orders.OrderItem",
        on_delete=models.CASCADE,
        related_name="return_requests"
    )
    reason = models.TextField()
    additional_info = models.TextField(blank=True, null=True)
    uploaded_images = models.ManyToManyField(
        "common.ImageUpload",
        related_name="return_requests",
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=ReturnStatus.choices,
        default=ReturnStatus.PENDING,
    )

    requested_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="return_requests"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["product", "status"])]

    def __str__(self):
        return f"Return request for {self.product.name} - {self.status}"

    def clean(self):
        if self.pk and self.uploaded_images.count() > 5:
            raise ValidationError("You can upload a maximum of 5 images for a return request.")