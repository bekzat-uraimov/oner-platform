"""entitlements — the single source of truth for access.

If a row exists for (user, course), the user owns the course. Nothing else grants
access: not the client, not a success redirect — only a verified payment or an
explicit admin grant writes here.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

from app.models.base import utcnow

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.purchase import Purchase
    from app.models.user import User


class Entitlement(SQLModel, table=True):
    __tablename__ = "entitlements"
    # One entitlement per (user, course) — owning twice is meaningless and would
    # let a duplicate webhook double-grant.
    __table_args__ = (UniqueConstraint("user_id", "course_id", name="uq_entitlement_user_course"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    granted_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
    source_purchase_id: int | None = Field(default=None, foreign_key="purchases.id")

    user: "User" = Relationship(back_populates="entitlements")
    course: "Course" = Relationship(back_populates="entitlements")
    source_purchase: Optional["Purchase"] = Relationship(back_populates="entitlement")
