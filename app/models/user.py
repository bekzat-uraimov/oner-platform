"""users — accounts. Students buy and watch; admins manage the catalog."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import UserRole, utcnow

if TYPE_CHECKING:
    from app.models.entitlement import Entitlement
    from app.models.purchase import Purchase


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=320)
    password_hash: str
    role: UserRole = Field(default=UserRole.student)
    # False locks the account out of login, refresh, playback and downloads on
    # its next request. A flag, not a delete, so purchases and ownership survive.
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))

    purchases: list["Purchase"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"foreign_keys": "[Purchase.user_id]"},
    )
    entitlements: list["Entitlement"] = Relationship(back_populates="user")
