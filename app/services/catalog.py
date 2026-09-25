"""Catalog reads. Who may see an unpublished course is decided here, in one place."""

from sqlmodel import Session, select

from app.models import Course, CourseStatus, Lesson, Module, User
from app.services.entitlements import can_access_course


def list_courses(session: Session, *, include_drafts: bool = False) -> list[Course]:
    # Oldest first, so the catalog doesn't reshuffle between requests.
    stmt = select(Course).order_by(Course.id)
    if not include_drafts:
        stmt = stmt.where(Course.status == CourseStatus.published)
    return list(session.exec(stmt).all())


def get_course_by_slug(session: Session, slug: str) -> Course | None:
    return session.exec(select(Course).where(Course.slug == slug)).first()


def is_visible(session: Session, course: Course, user: User | None) -> bool:
    """Published courses are public. An unpublished one stays visible to admins
    and to everyone who owns it: unpublishing takes a course out of the catalog,
    not away from the people who paid for it."""
    if course.status == CourseStatus.published:
        return True
    return user is not None and can_access_course(session, user, course.id)


def get_lesson_in_course(
    session: Session, course_id: int, lesson_id: int
) -> Lesson | None:
    """Fetch a lesson only if it actually belongs to the given course."""
    stmt = (
        select(Lesson)
        .join(Module, Module.id == Lesson.module_id)
        .where(Lesson.id == lesson_id, Module.course_id == course_id)
    )
    return session.exec(stmt).first()


def get_lesson_course(session: Session, lesson_id: int) -> Course | None:
    """The course a lesson belongs to. Needed when a request names only a
    lesson but the access rule lives on the course."""
    stmt = (
        select(Course)
        .join(Module, Module.course_id == Course.id)
        .join(Lesson, Lesson.module_id == Module.id)
        .where(Lesson.id == lesson_id)
    )
    return session.exec(stmt).first()


def get_courses_by_video_id(session: Session, video_id: str) -> list[Course]:
    """Every course containing this Kinescope video.

    Usually one, but the same lesson can be reused across courses, and owning
    any of them is enough to watch it. The DRM callback knows only the video id.
    """
    stmt = (
        select(Course)
        .join(Module, Module.course_id == Course.id)
        .join(Lesson, Lesson.module_id == Module.id)
        .where(Lesson.kinescope_video_id == video_id)
        .distinct()
    )
    return list(session.exec(stmt).all())
