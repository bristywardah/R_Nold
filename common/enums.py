from enum import Enum

class SavedProductStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"

    @classmethod
    def choices(cls):
        return [(status.value, status.name.replace('_', ' ').title()) for status in cls]
