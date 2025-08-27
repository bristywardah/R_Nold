from enum import Enum

class PayoutStatusEnum(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

    @classmethod
    def choices(cls):
        return [(key.value, key.name.capitalize()) for key in cls]
