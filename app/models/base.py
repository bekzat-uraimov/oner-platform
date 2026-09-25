"""Shared enums and helpers for the data model."""

from datetime import datetime, timezone
from enum import Enum


def utcnow() -> datetime:
    """Timezone-aware UTC now — used as the default for every timestamp column."""
    return datetime.now(timezone.utc)


class UserRole(str, Enum):
    student = "student"
    admin = "admin"


class CourseStatus(str, Enum):
    draft = "draft"
    published = "published"


class Currency(str, Enum):
    KGS = "KGS"
    KZT = "KZT"
    UZS = "UZS"
    USD = "USD"


class Gateway(str, Enum):
    freedompay = "freedompay"
    manual = "manual"  # admin grant / testing


class PurchaseStatus(str, Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"
    # Recorded by an admin after the money went back through FreedomPay's
    # merchant cabinet. Never set by a callback.
    refunded = "refunded"


class MaterialType(str, Enum):
    pdf = "pdf"
    zip = "zip"
    link = "link"
    other = "other"
