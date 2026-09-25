"""price_audit — an append-only trail of every price change, for accountability."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

from app.models.base import utcnow


class PriceAudit(SQLModel, table=True):
    __tablename__ = "price_audit"

    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    old_price: Decimal = Field(max_digits=12, decimal_places=2)
    new_price: Decimal = Field(max_digits=12, decimal_places=2)
    changed_by: int = Field(foreign_key="users.id")  # admin user id
    changed_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
