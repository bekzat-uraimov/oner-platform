"""Import every model so SQLModel.metadata sees all tables.

Anything that needs the full schema (Alembic autogenerate, create_all in tests)
just imports this package.
"""

from app.models.base import (
    CourseStatus,
    Currency,
    Gateway,
    MaterialType,
    PurchaseStatus,
    UserRole,
)
from app.models.course import Course
from app.models.entitlement import Entitlement
from app.models.lesson import Lesson
from app.models.material import Material
from app.models.module import Module
from app.models.price_audit import PriceAudit
from app.models.purchase import Purchase
from app.models.user import User

__all__ = [
    "Course",
    "CourseStatus",
    "Currency",
    "Entitlement",
    "Gateway",
    "Lesson",
    "Material",
    "MaterialType",
    "Module",
    "PriceAudit",
    "Purchase",
    "PurchaseStatus",
    "User",
    "UserRole",
]
