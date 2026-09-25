"""Kinescope's playback authorization callback.

Kinescope calls this on every play attempt, passing the drmauthtoken our own
/video/{id}/token minted. 200 releases the decryption key, 403 withholds it.
Register the URL once per project:

    PUT https://api.kinescope.io/v1/drm/auth/${KINESCOPE_PROJECT_ID}
"""

import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.schemas import DrmAuthRequest
from app.services.video import authorize_playback

log = logging.getLogger(__name__)

router = APIRouter(prefix="/drm", tags=["drm"])

basic_scheme = HTTPBasic(auto_error=False)


def verify_kinescope(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(basic_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Basic Auth, when configured.

    Kinescope offers no request signature, so this is the only transport check
    available. It's defence in depth, not the gate — the signed token is what
    actually decides, which is why an unconfigured deployment still works.
    """
    if not settings.kinescope_drm_auth_user:
        return

    user_ok = credentials is not None and secrets.compare_digest(
        credentials.username, settings.kinescope_drm_auth_user
    )
    password_ok = credentials is not None and secrets.compare_digest(
        credentials.password, settings.kinescope_drm_auth_password
    )
    if not (user_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


@router.post("/auth", dependencies=[Depends(verify_kinescope)])
def drm_auth(
    body: DrmAuthRequest,
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    if not body.id or not body.token:
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    if not authorize_playback(session, body.token, body.id):
        # Never say why. A denied viewer learns nothing about which half failed.
        log.info("drm playback denied for video %s", body.id)
        return Response(status_code=status.HTTP_403_FORBIDDEN)

    return Response(status_code=status.HTTP_200_OK)
