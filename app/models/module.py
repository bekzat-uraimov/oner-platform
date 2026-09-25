"""modules — ordered sections inside a course."""

from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.lesson import Lesson


class Module(SQLModel, table=True):
    __tablename__ = "modules"

    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    title: str
    description: str | None = None
    order: int = Field(default=0)

    course: "Course" = Relationship(back_populates="modules")
    lessons: list["Lesson"] = Relationship(
        back_populates="module",
        sa_relationship_kwargs={"order_by": "Lesson.order", "cascade": "all, delete-orphan"},
    )
