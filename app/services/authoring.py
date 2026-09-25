"""Authoring — the admin write path for the catalog.

catalog.py reads, and nearly everything it does is hiding: drafts from the
public, video ids from non-owners. An author needs the opposite view, so the
write rules live here rather than growing flags on the read functions.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from app.models import (
    Course,
    Entitlement,
    Lesson,
    Material,
    MaterialType,
    Module,
    PriceAudit,
    Purchase,
)
from app.services.lesson_video import unused_videos
from app.services.storage import is_material_key


class SlugTaken(Exception):
    """Another course already uses this slug."""


class CourseHasSales(Exception):
    """Someone has bought this course, so it can't be deleted."""


class BadStorageKey(Exception):
    """The key didn't come from our own upload-url route."""


class KeyAlreadyRecorded(Exception):
    """A material row already points at this object."""


@dataclass
class Removed:
    """What a delete left outside the database, for the caller to clean up once
    the response is out: R2 files, and Kinescope videos no lesson uses any more."""

    storage_keys: list[str] = field(default_factory=list)
    video_ids: list[str] = field(default_factory=list)


def _videos_of(lessons) -> list[str]:
    return [
        video_id
        for lesson in lessons
        for video_id in (lesson.kinescope_video_id, lesson.pending_video_id)
        if video_id
    ]


def _next_module_order(session: Session, course_id: int) -> int:
    top = session.exec(
        select(func.max(Module.order)).where(Module.course_id == course_id)
    ).one()
    return 0 if top is None else top + 1


def _next_lesson_order(session: Session, module_id: int) -> int:
    top = session.exec(
        select(func.max(Lesson.order)).where(Lesson.module_id == module_id)
    ).one()
    return 0 if top is None else top + 1


def _apply(session: Session, obj, fields: dict):
    for key, value in fields.items():
        setattr(obj, key, value)
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def _drop_materials(
    session: Session, *, course_id: int | None = None, lesson_ids: Sequence[int] = ()
) -> list[str]:
    """Delete material rows that would dangle once their parent is gone, and
    return their storage keys.

    Rows only. Their files go after the commit (cleanup.reclaim): deleting files
    first would leave rows pointing at nothing if the commit then failed.
    """
    rows = []
    if course_id is not None:
        rows += session.exec(
            select(Material)
            .where(Material.course_id == course_id)
            .order_by(Material.id)
        ).all()
    if lesson_ids:
        rows += session.exec(
            select(Material)
            .where(Material.lesson_id.in_(lesson_ids))
            .order_by(Material.id)
        ).all()
    for row in rows:
        session.delete(row)
    return [row.storage_key for row in rows]


# ---- courses --------------------------------------------------------------


def create_course(session: Session, fields: dict) -> Course:
    course = Course(**fields)
    session.add(course)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise SlugTaken(fields.get("slug"))
    session.refresh(course)
    return course


def update_course(
    session: Session, course: Course, fields: dict, *, admin_id: int
) -> Course:
    """Partial update. A price change also writes the price_audit trail."""
    price = fields.get("price")
    if price is not None and price != course.price:
        session.add(
            PriceAudit(
                course_id=course.id,
                old_price=course.price,
                new_price=price,
                changed_by=admin_id,
            )
        )

    for key, value in fields.items():
        setattr(course, key, value)

    session.add(course)
    try:
        session.commit()
    except IntegrityError:
        # Same transaction, so the audit row rolls back with the change.
        session.rollback()
        raise SlugTaken(fields.get("slug"))
    session.refresh(course)
    return course


def has_sales(session: Session, course_id: int) -> bool:
    owned = session.exec(
        select(Entitlement.id).where(Entitlement.course_id == course_id)
    ).first()
    if owned is not None:
        return True
    # Any purchase counts, including failed and abandoned ones: they're the
    # conversion record, and their foreign key would block the delete anyway.
    attempted = session.exec(
        select(Purchase.id).where(Purchase.course_id == course_id)
    ).first()
    return attempted is not None


def delete_course(session: Session, course: Course) -> Removed:
    """Delete a course and its whole tree.

    Refused once anyone has bought it — unpublish instead. A sale is a record we
    keep even after the course is retired. Returns the files and videos it left
    behind.
    """
    if has_sales(session, course.id):
        raise CourseHasSales(f"course {course.id}")

    lessons = session.exec(
        select(Lesson)
        .join(Module, Module.id == Lesson.module_id)
        .where(Module.course_id == course.id)
    ).all()
    videos = _videos_of(lessons)
    keys = _drop_materials(
        session, course_id=course.id, lesson_ids=[lesson.id for lesson in lessons]
    )

    # Nobody bought it, so nobody was ever charged any of these prices; the
    # history has nothing left to account for, and its foreign key would
    # block the delete.
    for row in session.exec(
        select(PriceAudit).where(PriceAudit.course_id == course.id)
    ).all():
        session.delete(row)

    # cascade="all, delete-orphan" on the relationships takes modules + lessons.
    session.delete(course)
    session.commit()
    return Removed(keys, unused_videos(session, videos))


# ---- modules --------------------------------------------------------------


def create_module(session: Session, course: Course, fields: dict) -> Module:
    order = fields.get("order")
    module = Module(
        course_id=course.id,
        title=fields["title"],
        description=fields.get("description"),
        order=_next_module_order(session, course.id) if order is None else order,
    )
    session.add(module)
    session.commit()
    session.refresh(module)
    return module


def update_module(session: Session, module: Module, fields: dict) -> Module:
    return _apply(session, module, fields)


def delete_module(session: Session, module: Module) -> Removed:
    videos = _videos_of(module.lessons)
    keys = _drop_materials(session, lesson_ids=[lesson.id for lesson in module.lessons])
    session.delete(module)
    session.commit()
    return Removed(keys, unused_videos(session, videos))


# ---- lessons --------------------------------------------------------------


def create_lesson(session: Session, module: Module, fields: dict) -> Lesson:
    order = fields.get("order")
    lesson = Lesson(
        module_id=module.id,
        title=fields["title"],
        description=fields.get("description"),
        order=_next_lesson_order(session, module.id) if order is None else order,
        duration=fields.get("duration"),
        kinescope_video_id=fields.get("kinescope_video_id"),
    )
    session.add(lesson)
    session.commit()
    session.refresh(lesson)
    return lesson


def update_lesson(session: Session, lesson: Lesson, fields: dict) -> Lesson:
    return _apply(session, lesson, fields)


def delete_lesson(session: Session, lesson: Lesson) -> Removed:
    videos = _videos_of([lesson])
    keys = _drop_materials(session, lesson_ids=[lesson.id])
    session.delete(lesson)
    session.commit()
    return Removed(keys, unused_videos(session, videos))


# ---- materials ------------------------------------------------------------

_TYPE_BY_SUFFIX = {".pdf": MaterialType.pdf, ".zip": MaterialType.zip}


def material_type_for(storage_key: str) -> MaterialType:
    return _TYPE_BY_SUFFIX.get(
        PurePosixPath(storage_key).suffix.lower(), MaterialType.other
    )


def create_material(session: Session, fields: dict) -> Material:
    """Record an already-uploaded object. The bytes went straight to R2."""
    if not is_material_key(fields["storage_key"]):
        raise BadStorageKey(fields["storage_key"])

    material = Material(
        title=fields["title"],
        storage_key=fields["storage_key"],
        type=fields.get("type") or material_type_for(fields["storage_key"]),
        course_id=fields.get("course_id"),
        lesson_id=fields.get("lesson_id"),
    )
    session.add(material)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise KeyAlreadyRecorded(fields["storage_key"])
    session.refresh(material)
    return material


def update_material(session: Session, material: Material, fields: dict) -> Material:
    return _apply(session, material, fields)


def delete_material(session: Session, material: Material) -> Removed:
    key = material.storage_key
    session.delete(material)
    session.commit()
    return Removed(storage_keys=[key])
