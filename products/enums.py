from django.db import models

class ProductStatus(models.TextChoices):
    PENDING = "pending", "Pending" 
    DRAFT = "draft", "Draft"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    ARCHIVED = "archived", "Archived"

class DiscountType(models.TextChoices):
    PERCENTAGE = "percentage", "Percentage (%)"
    FLAT = "flat", "Flat Amount ($)"


class ReturnStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"