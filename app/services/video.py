"""Video access: issuing a DRM token, and answering Kinescope's playback check.

Two halves of one rule. `issue_drm_token` decides who may ever hold a token;
`authorize_playback` decides, at the moment of playback, whether the key is
released. The second is the real gate — Kinescope calls it on every play — but
binding the token to a video means a bug in one doesn't hand out the other.
"""

from sqlmodel import Session

from app.core.security import DRM, JWTError, create_drm_token, decode_token
from app.models import Lesson, User
from app.services.catalog import get_courses_by_video_id, get_lesson_course, is_visible
from app.services.entitlements import can_access_course


class LessonNotFound(Exception):
    """No such lesson, or one the caller isn't allowed to know exists."""


class NoVideo(Exception):
    """The lesson is real but has no video attached yet."""


class AccessDenied(Exception):
    """The lesson exists and the caller may know it, but doesn't own it."""


def issue_drm_token(session: Session, user: User, lesson_id: int) -> tuple[str, str]:
    """Return (video_id, drm token) for a lesson the user owns."""
    lesson = session.get(Lesson, lesson_id)
    course = get_lesson_course(session, lesson_id) if lesson else None
    if course is None:
        raise LessonNotFound(f"lesson {lesson_id}")

    # Unpublished courses 404 for everyone but admins and owners, as in the catalog.
    if not is_visible(session, course, user):
        raise LessonNotFound(f"lesson {lesson_id}")

    # Ownership before existence-of-video: a non-owner shouldn't learn which
    # lessons have footage yet.
    if not can_access_course(session, user, course.id):
        raise AccessDenied(f"user {user.id} does not own course {course.id}")

    if not lesson.kinescope_video_id:
        raise NoVideo(f"lesson {lesson_id} has no video")

    return lesson.kinescope_video_id, create_drm_token(user.id, lesson.kinescope_video_id)


def authorize_playback(session: Session, token: str, video_id: str) -> bool:
    """Kinescope's question: release the decryption key for this video?

    Every failure is the same answer. Ownership is re-read here rather than
    trusted from the token, so a refund revokes playback within the token's TTL.
    """
    try:
        payload = decode_token(token)
    except JWTError:
        return False

    # An access token must never double as a playback key.
    if payload.get("type") != DRM:
        return False

    # The token is minted for one video. Kinescope tells us which one is playing.
    if payload.get("vid") != video_id:
        return False

    sub = payload.get("sub")
    if sub is None:
        return False
    user = session.get(User, int(sub))
    if user is None or not user.is_active:
        return False

    courses = get_courses_by_video_id(session, video_id)
    return any(can_access_course(session, user, c.id) for c in courses)
