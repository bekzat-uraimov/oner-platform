"""Video routes for the owner. Hands out the DRM token the player needs."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.api.deps import CurrentUser
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.schemas import DrmTokenResponse
from app.services.video import AccessDenied, LessonNotFound, NoVideo, issue_drm_token

router = APIRouter(prefix="/video", tags=["video"])


@router.post("/{lesson_id}/token", response_model=DrmTokenResponse)
def create_video_token(
    lesson_id: int,
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        video_id, token = issue_drm_token(session, user, lesson_id)
    except LessonNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found"
        )
    except AccessDenied:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You do not own this course"
        )
    except NoVideo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Lesson has no video yet"
        )

    return DrmTokenResponse(
        video_id=video_id,
        drm_auth_token=token,
        expires_in=settings.drm_token_ttl_min * 60,
    )
