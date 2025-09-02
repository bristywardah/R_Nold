from users.models import BaseModel
from django.db import models
from django.utils.text import slugify
import uuid
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
from common.enums import SavedProductStatus
import os

User = settings.AUTH_USER_MODEL


def upload_to(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join("uploads/common/", filename)


class ImageUpload(BaseModel):
    image = models.ImageField(upload_to=upload_to)
    alt_text = models.CharField(max_length=255, blank=True, help_text="Optional alt text for SEO/accessibility")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_images"
    )

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.alt_text or f"Image {self.pk}"




class Category(BaseModel):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    image = models.ImageField(null=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["slug"]), models.Index(fields=["name"])]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or str(uuid.uuid4())[:8]
            slug = base
            i = 1
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)







class Tag(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["slug"]), models.Index(fields=["name"])]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or str(uuid.uuid4())[:8]
            slug = base
            i = 1
            while Tag.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)


class SEO(models.Model):
    title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)

    def __str__(self):
        return self.title or "SEO Settings"


class SavedProduct(BaseModel):
    vendor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="saved_products",
        limit_choices_to={"role": "vendor"},
    )
    name = models.CharField(max_length=255, blank=True)
    data = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=30,
        choices=SavedProductStatus.choices(),
        default=SavedProductStatus.DRAFT.value,
    )

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["vendor"])]

    def __str__(self):
        return self.name or f"Draft #{self.pk}"




class Banner(BaseModel):
    title = models.CharField(max_length=255, blank=True)
    subtitle = models.CharField(max_length=255, blank=True)
    image = models.ImageField(upload_to=upload_to)
    link = models.URLField(max_length=500, blank=True, null=True)
    alt_text = models.CharField(max_length=255, blank=True)
    position = models.PositiveSmallIntegerField(default=0, help_text="Position in the banner rotation")
    start_datetime = models.DateTimeField(blank=True, null=True)
    end_datetime = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True, help_text="Is this banner currently active?")

    class Meta:
        ordering = ["position", "-created_at"]
        indexes = [models.Index(fields=["position"])]

    def __str__(self):
        return f"Banner {self.pk} - {self.alt_text or 'No Alt Text'}"









class Wishlist(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wishlists")
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, related_name="wishlisted_by")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "product")
        ordering = ["-added_at"]
        indexes = [models.Index(fields=["user", "product"])]

    def __str__(self):
        return f"{self.user.email} - {self.product.name}"