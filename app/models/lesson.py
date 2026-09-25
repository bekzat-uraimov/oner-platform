"""lessons — a single video unit. The Kinescope video id is gated by entitlement."""

from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.material import Material
    from app.models.module import Module


class Lesson(SQLModel, table=True):
    __tablename__ = "lessons"

    id: int | None = Field(default=None, primary_key=True)
    module_id: int = Field(foreign_key="modules.id", index=True)
    title: str
    description: str | None = None
    order: int = Field(default=0)
    # Looked up on every playback authorization callback, so it's indexed.
    kinescope_video_id: str | None = Field(default=None, index=True)
    # An upload still processing. It replaces kinescope_video_id once Kinescope
    # reports it done; indexed for the status webhook's lookup.
    pending_video_id: str | None = Field(default=None, index=True)
    duration: int | None = None  # seconds

    module: "Module" = Relationship(back_populates="lessons")
    materials: list["Material"] = Relationship(
        back_populates="lesson", sa_relationship_kwargs={"order_by": "Material.id"}
    )
