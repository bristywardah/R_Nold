from enum import Enum


class UserRole(Enum):
    ADMIN = "admin"
    VENDOR = "vendor"
    CUSTOMER = "customer"

    @classmethod
    def choices(cls):
        return [(role.value, role.name.title()) for role in cls]


class SellerApplicationStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"

    @classmethod
    def choices(cls):
        return [(status.value, status.name.title()) for status in cls]
