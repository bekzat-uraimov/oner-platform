"""materials — downloadables. Attached to a lesson OR a course (exactly one)."""

from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

from app.models.base import MaterialType

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.lesson import Lesson


class Material(SQLModel, table=True):
    __tablename__ = "materials"
    # One row per stored object, so deleting a row can safely delete its file.
    __table_args__ = (UniqueConstraint("storage_key", name="uq_material_storage_key"),)

    id: int | None = Field(default=None, primary_key=True)
    lesson_id: int | None = Field(default=None, foreign_key="lessons.id", index=True)
    course_id: int | None = Field(default=None, foreign_key="courses.id", index=True)
    title: str
    storage_key: str  # Cloudflare R2 object key
    type: MaterialType = Field(default=MaterialType.other)

    lesson: Optional["Lesson"] = Relationship(back_populates="materials")
    course: Optional["Course"] = Relationship(back_populates="materials")
