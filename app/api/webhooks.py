"""Gateway callbacks. Server-to-server, unauthenticated, and the only place
where a payment becomes access.

The browser's success_url is decoration; this endpoint is the source of truth.
No rate limit here on purpose — throttling FreedomPay would drop real payments.

Kinescope's status webhook lives here too. It can't grant anything: it only
says which lesson to re-check, and the status is read back from Kinescope.
"""

import logging
import secrets
from typing import Annotated

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlmodel import Session, select

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.models import Lesson
from app.schemas import KinescopeWebhook
from app.services.freedompay import FreedomPayClient, build_response, get_gateway, script_name
from app.services.kinescope import (
    KinescopeClient,
    KinescopeError,
    KinescopeNotConfigured,
    get_kinescope,
)
from app.services.lesson_video import delete_videos, refresh
from app.services.payments import PaymentRefused, ResultRejected, settle_payment

log = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# A result callback is a few hundred bytes. The endpoint is unauthenticated and
# form bodies are buffered in memory, so cap it well above real traffic.
MAX_BODY = 64 * 1024

# Shown to the buyer on FreedomPay's page when we refuse a duplicate payment.
REFUSED_REASON = "Курс уже оплачен, повторный платёж отменён"


async def form_params(request: Request) -> dict[str, str]:
    """Every field FreedomPay posted, untouched.

    The signature covers all of them, so parsing into a fixed schema would break
    verification the day they add a field. Validation happens after the
    signature check, not instead of it.
    """
    length = request.headers.get("content-length")
    if length is not None and length.isdigit() and int(length) > MAX_BODY:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Callback body too large",
        )

    form = await request.form()
    return {key: str(value) for key, value in form.items()}


def _xml(gateway: FreedomPayClient, status: str, description: str | None = None) -> Response:
    body = build_response(
        script_name(gateway.result_url),
        gateway.secret_key,
        status=status,
        description=description,
    )
    return Response(content=body, media_type="application/xml")


@router.post("/freedompay/result")
def freedompay_result(
    params: Annotated[dict[str, str], Depends(form_params)],
    session: Annotated[Session, Depends(get_session)],
    gateway: Annotated[FreedomPayClient, Depends(get_gateway)],
) -> Response:
    try:
        purchase = settle_payment(session, gateway, params)
    except ResultRejected as e:
        # 200 with pg_status=error, not a 5xx: retrying a forged signature or a
        # mismatched amount will fail identically for two hours. Anything
        # genuinely transient raises instead, and their retries handle it.
        log.warning("freedompay callback rejected: %s", e)
        return _xml(gateway, "error", str(e))
    except PaymentRefused as e:
        # FreedomPay cancels the payment and shows the buyer this reason.
        log.warning("freedompay duplicate payment refused: %s", e)
        return _xml(gateway, "rejected", REFUSED_REASON)

    log.info("freedompay callback settled purchase %s as %s", purchase.id, purchase.status)
    return _xml(gateway, "ok")


# ---- Kinescope ------------------------------------------------------------------

basic_scheme = HTTPBasic(auto_error=False)


def verify_kinescope_webhook(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(basic_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """The Basic Auth pair registered with the webhook is the only proof a call
    came from Kinescope, which signs nothing. Unconfigured means closed: every
    call spends a request against Kinescope's API rate limit."""
    if not settings.kinescope_webhook_user:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Kinescope webhook is not configured",
        )
    user_ok = credentials is not None and secrets.compare_digest(
        credentials.username, settings.kinescope_webhook_user
    )
    password_ok = credentials is not None and secrets.compare_digest(
        credentials.password, settings.kinescope_webhook_password
    )
    if not (user_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


@router.post("/kinescope", dependencies=[Depends(verify_kinescope_webhook)])
def kinescope_status(
    body: KinescopeWebhook,
    session: Annotated[Session, Depends(get_session)],
    kinescope: Annotated[KinescopeClient, Depends(get_kinescope)],
    background: BackgroundTasks,
) -> Response:
    video_id = body.data.id if body.data else None
    # Anything we don't act on still gets a 200: a retry wouldn't change it.
    if body.event != "media.update.status" or not video_id:
        return Response(status_code=status.HTTP_200_OK)
    lesson = session.exec(select(Lesson).where(Lesson.pending_video_id == video_id)).first()
    if lesson is None:
        return Response(status_code=status.HTTP_200_OK)

    try:
        state, unused = refresh(session, kinescope, lesson)
    except (KinescopeNotConfigured, KinescopeError, httpx.HTTPError) as e:
        # A 5xx makes Kinescope retry, and the API may be back by then.
        log.warning("kinescope webhook for %s could not check status: %s", video_id, e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not reach Kinescope"
        )
    background.add_task(delete_videos, kinescope, unused)
    log.info("kinescope webhook: lesson %s upload %s is %s", lesson.id, video_id, state)
    return Response(status_code=status.HTTP_200_OK)
