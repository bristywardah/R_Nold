from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.auth.base_user import BaseUserManager
from django.db import models
from django.utils import timezone
from django.conf import settings
from users.enums import UserRole, SellerApplicationStatus


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The Email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', UserRole.ADMIN.value)
        extra_fields.setdefault('agree_to_terms', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        if extra_fields.get('role') != UserRole.ADMIN.value:
            raise ValueError('Superuser must have role of admin.')
        if extra_fields.get('agree_to_terms') is not True:
            raise ValueError('Superuser must agree to the terms.')
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    email = models.EmailField(unique=True)
    profile_image = models.ImageField(upload_to="profiles/", blank=True, null=True)
    cover_image = models.ImageField(upload_to="covers/", blank=True, null=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    secondary_number = models.CharField(max_length=20, blank=True)
    emergency_contact = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    gender = models.CharField(
        max_length=10,
        blank=True,
        choices=[
            ("male", "Male"),
            ("female", "Female"),
            ("other", "Other"),
        ]
    )
    date_of_birth = models.DateField(blank=True, null=True)
    national_id = models.CharField(max_length=50, blank=True)
    role = models.CharField(max_length=20, choices=UserRole.choices(), default=UserRole.CUSTOMER.value)
    agree_to_terms = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    otp_code = models.CharField(max_length=6, blank=True, null=True)
    otp_created_at = models.DateTimeField(blank=True, null=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def generate_otp(self):
        import random
        otp = ''.join(random.choices('0123456789', k=6))
        self.otp_code = otp
        self.otp_created_at = timezone.now()
        self.save(update_fields=['otp_code', 'otp_created_at'])
        return otp

    def __str__(self):
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name if full_name else self.email


class SellerOwnerImage(BaseModel):
    image = models.ImageField(upload_to="seller/owners/")

    def __str__(self):
        return f"Owner Image {self.id}"




class SellerApplication(BaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seller_application"
    )

    # Contact Info
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    job_title = models.CharField(max_length=150, blank=True)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)

    # Business Info
    legal_business_name = models.CharField(max_length=255)
    business_address = models.TextField()
    country = models.CharField(max_length=100)
    city_town = models.CharField(max_length=100)
    state_province = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20)
    established_date = models.DateField()
    business_type = models.CharField(max_length=100)
    taxpayer_number = models.CharField(max_length=100, blank=True)
    trade_register_number = models.CharField(max_length=100, blank=True)

    status = models.CharField(max_length=20, choices=SellerApplicationStatus.choices(), default=SellerApplicationStatus.PENDING.value)

    # Verification Docs
    nid_front = models.ImageField(upload_to="seller/nid/front/")
    nid_back = models.ImageField(upload_to="seller/nid/back/")
    # Removed business_owner_images field
    owner_images = models.ManyToManyField(SellerOwnerImage, blank=True)

    # Localization Plans
    home_localization_plan = models.TextField(blank=True, null=True)
    business_localization_plan = models.TextField(blank=True, null=True)

    taxpayer_doc = models.FileField(upload_to="seller/taxpayer/", blank=True, null=True)
    trade_register_doc = models.FileField(upload_to="seller/trade_register/", blank=True, null=True)

    verification_code = models.CharField(max_length=10, blank=True, null=True)

    def __str__(self):
        return f"Seller Application - {self.user.email} - {self.status}"
