"""Public catalog routes. Anonymous visitors see published courses; admins see
drafts, and owners keep seeing a course after it's unpublished. No endpoint here
exposes a playable video id."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.api.deps import CurrentUser, OptionalUser
from app.core.db import get_session
from app.models import UserRole
from app.schemas import CourseDetail, CourseListItem, LessonDetail, MaterialPublic
from app.services.catalog import (
    get_course_by_slug,
    get_lesson_in_course,
    is_visible,
    list_courses,
)
from app.services.entitlements import can_access_course

router = APIRouter(prefix="/courses", tags=["catalog"])


def _can_see_drafts(user: OptionalUser) -> bool:
    return user is not None and user.role == UserRole.admin


@router.get("", response_model=list[CourseListItem])
def list_published_courses(
    user: OptionalUser,
    session: Annotated[Session, Depends(get_session)],
):
    return list_courses(session, include_drafts=_can_see_drafts(user))


@router.get("/{slug}", response_model=CourseDetail)
def get_course(
    slug: str,
    user: OptionalUser,
    session: Annotated[Session, Depends(get_session)],
):
    course = get_course_by_slug(session, slug)
    if course is None or not is_visible(session, course, user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )
    return course


@router.get("/{slug}/lessons/{lesson_id}", response_model=LessonDetail)
def get_lesson_detail(
    slug: str,
    lesson_id: int,
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
):
    """Lesson detail, gated by ownership. Admins see any lesson; everyone else
    must own the course. Returns 404 (not 403) for a non-existent course/lesson
    so we don't leak which slugs exist."""
    course = get_course_by_slug(session, slug)
    if course is None or not is_visible(session, course, user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )

    lesson = get_lesson_in_course(session, course.id, lesson_id)
    if lesson is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found"
        )

    if not can_access_course(session, user, course.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this course",
        )

    return LessonDetail(
        id=lesson.id,
        module_id=lesson.module_id,
        title=lesson.title,
        order=lesson.order,
        description=lesson.description,
        duration=lesson.duration,
        # The same check issue_drm_token makes, so this can't promise a video
        # the token route then refuses.
        video_available=bool(lesson.kinescope_video_id),
        materials=[MaterialPublic.model_validate(m) for m in lesson.materials],
    )
