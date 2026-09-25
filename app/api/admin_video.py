"""Admin routes for a lesson's video.

    1. POST   /admin/lessons/{id}/video/upload   a Tus endpoint for the browser
    2. the browser uploads the file there with tus-js-client, never through us
    3. GET    /admin/lessons/{id}/video          status; swaps the video in once done
                                                 (Kinescope's webhook does this too)
       DELETE /admin/lessons/{id}/video/pending  give up on an upload
"""

from typing import Annotated

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlmodel import Session

from app.api.deps import AdminUser
from app.core.db import get_session
from app.models import Lesson
from app.schemas import LessonVideo, VideoUploadRequest, VideoUploadTarget
from app.services.kinescope import (
    KinescopeClient,
    KinescopeError,
    KinescopeNotConfigured,
    get_kinescope,
)
from app.services.lesson_video import (
    NoPendingUpload,
    delete_videos,
    discard_upload,
    refresh,
    start_upload,
    upload_state,
)

router = APIRouter(prefix="/admin", tags=["admin"])

SessionDep = Annotated[Session, Depends(get_session)]
KinescopeDep = Annotated[KinescopeClient, Depends(get_kinescope)]


def _lesson(session: Session, lesson_id: int) -> Lesson:
    lesson = session.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    return lesson


def _unavailable(e: Exception) -> HTTPException:
    if isinstance(e, KinescopeNotConfigured):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Video uploads are unavailable",
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY, detail="Kinescope did not respond"
    )


def _state(lesson: Lesson, pending_status: str | None) -> LessonVideo:
    return LessonVideo(
        video_id=lesson.kinescope_video_id,
        pending_video_id=lesson.pending_video_id,
        pending_status=pending_status,
        state=upload_state(lesson, pending_status),
        duration=lesson.duration,
    )


@router.post("/lessons/{lesson_id}/video/upload", response_model=VideoUploadTarget)
def upload_video(
    lesson_id: int,
    body: VideoUploadRequest,
    _admin: AdminUser,
    session: SessionDep,
    kinescope: KinescopeDep,
    background: BackgroundTasks,
):
    lesson = _lesson(session, lesson_id)
    try:
        link, unused = start_upload(
            session, kinescope, lesson, filename=body.filename, filesize=body.filesize
        )
    except (KinescopeNotConfigured, KinescopeError, httpx.HTTPError) as e:
        raise _unavailable(e)
    background.add_task(delete_videos, kinescope, unused)
    return VideoUploadTarget(video_id=link.video_id, endpoint=link.endpoint)


@router.get("/lessons/{lesson_id}/video", response_model=LessonVideo)
def lesson_video(
    lesson_id: int,
    _admin: AdminUser,
    session: SessionDep,
    kinescope: KinescopeDep,
    background: BackgroundTasks,
):
    """Where the lesson's video stands. A pending upload is checked with
    Kinescope and swapped in if processing has finished."""
    lesson = _lesson(session, lesson_id)
    try:
        pending_status, unused = refresh(session, kinescope, lesson)
    except (KinescopeNotConfigured, KinescopeError, httpx.HTTPError) as e:
        raise _unavailable(e)
    background.add_task(delete_videos, kinescope, unused)
    return _state(lesson, pending_status)


@router.delete("/lessons/{lesson_id}/video/pending", status_code=status.HTTP_204_NO_CONTENT)
def discard_pending_video(
    lesson_id: int,
    _admin: AdminUser,
    session: SessionDep,
    kinescope: KinescopeDep,
    background: BackgroundTasks,
):
    lesson = _lesson(session, lesson_id)
    try:
        unused = discard_upload(session, lesson)
    except NoPendingUpload:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No upload in progress"
        )
    background.add_task(delete_videos, kinescope, unused)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
