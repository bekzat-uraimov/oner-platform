"""courses — the sellable unit. Holds modules → lessons and course-level materials."""

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.models.base import CourseStatus, Currency

if TYPE_CHECKING:
    from app.models.entitlement import Entitlement
    from app.models.material import Material
    from app.models.module import Module
    from app.models.purchase import Purchase


class Course(SQLModel, table=True):
    __tablename__ = "courses"

    id: int | None = Field(default=None, primary_key=True)
    title: str
    slug: str = Field(unique=True, index=True)
    description: str | None = None
    # Free text for the course page's "What you'll learn" and "Requirements".
    learning_outcomes: str | None = None
    requirements: str | None = None
    segment: str | None = None  # audience / category label
    price: Decimal = Field(default=Decimal("0"), max_digits=12, decimal_places=2)
    currency: Currency = Field(default=Currency.KGS)
    status: CourseStatus = Field(default=CourseStatus.draft, index=True)
    cover: str | None = None  # storage key / URL for the cover image

    modules: list["Module"] = Relationship(
        back_populates="course",
        sa_relationship_kwargs={"order_by": "Module.order", "cascade": "all, delete-orphan"},
    )
    materials: list["Material"] = Relationship(
        back_populates="course", sa_relationship_kwargs={"order_by": "Material.id"}
    )
    purchases: list["Purchase"] = Relationship(back_populates="course")
    entitlements: list["Entitlement"] = Relationship(back_populates="course")
