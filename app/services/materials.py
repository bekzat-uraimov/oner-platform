"""Material downloads, gated by ownership.

A material hangs off either a lesson or a course, but ownership is always
recorded per course — so the first job is finding which course a file belongs to.
"""

from sqlmodel import Session

from app.models import Course, Material, User
from app.services.catalog import get_lesson_course, is_visible
from app.services.entitlements import can_access_course
from app.services.storage import R2Client, download_filename


class MaterialNotFound(Exception):
    """No such material, or one the caller isn't allowed to know exists."""


class AccessDenied(Exception):
    """Real material on a real course the caller doesn't own."""


def material_course(session: Session, material: Material) -> Course | None:
    if material.course_id is not None:
        return session.get(Course, material.course_id)
    if material.lesson_id is not None:
        return get_lesson_course(session, material.lesson_id)
    return None


def download_url_for(
    session: Session, storage: R2Client, user: User, material_id: int
) -> tuple[Material, str, str]:
    """Return (material, filename, signed URL) for a material the user owns."""
    material = session.get(Material, material_id)
    course = material_course(session, material) if material else None
    if course is None:
        raise MaterialNotFound(f"material {material_id}")

    if not is_visible(session, course, user):
        raise MaterialNotFound(f"material {material_id}")

    if not can_access_course(session, user, course.id):
        raise AccessDenied(f"user {user.id} does not own course {course.id}")

    filename = download_filename(material.title, material.storage_key)
    return material, filename, storage.download_url(material.storage_key, filename)
