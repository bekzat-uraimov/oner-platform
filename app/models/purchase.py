"""purchases — a payment attempt. Unique gateway txn id makes webhooks idempotent."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Index, text
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import Currency, Gateway, PurchaseStatus, utcnow

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.entitlement import Entitlement
    from app.models.user import User


class Purchase(SQLModel, table=True):
    __tablename__ = "purchases"
    # One open order per buyer, course and price. Two Buy clicks at the same
    # moment would otherwise open two orders, and paying both charges twice.
    __table_args__ = (
        Index(
            "uq_pending_purchase",
            "user_id",
            "course_id",
            "amount",
            "currency",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    gateway: Gateway = Field(default=Gateway.freedompay)
    # Unique per gateway txn — the dedupe key that stops double-grants. Null until the
    # gateway assigns one (e.g. pending purchase before redirect).
    gateway_txn_id: str | None = Field(default=None, unique=True, index=True)
    amount: Decimal = Field(default=Decimal("0"), max_digits=12, decimal_places=2)
    currency: Currency = Field(default=Currency.KGS)
    status: PurchaseStatus = Field(default=PurchaseStatus.pending, index=True)
    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
    refunded_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    refunded_by: int | None = Field(default=None, foreign_key="users.id")  # admin user id
    refund_note: str | None = Field(default=None)

    # Two keys point at users now, so say which one makes a purchase someone's.
    user: "User" = Relationship(
        back_populates="purchases",
        sa_relationship_kwargs={"foreign_keys": "[Purchase.user_id]"},
    )
    course: "Course" = Relationship(back_populates="purchases")
    entitlement: Optional["Entitlement"] = Relationship(back_populates="source_purchase")
