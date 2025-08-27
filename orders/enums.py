from enum import Enum

class OrderStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"

    @classmethod
    def choices(cls):
        return [(status.value, status.name.capitalize()) for status in cls]

class DeliveryType(Enum):
    STANDARD = "standard"
    EXPRESS = "express"
    PICKUP = "pickup"

    @classmethod
    def choices(cls):
        return [(delivery.value, delivery.name.capitalize()) for delivery in cls]

class PaymentMethod(Enum):
    CASH = "cash"
    ONLINE = "online"

    @classmethod
    def choices(cls):
        return [(pm.value, pm.name.capitalize()) for pm in cls]
