"""Checkout route. Hands back a FreedomPay payment link and grants nothing."""

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session

from app.api.deps import CurrentUser
from app.core.db import get_session
from app.core.limiter import CHECKOUT_RATE_LIMIT, limiter
from app.models import Course, CourseStatus
from app.schemas import CheckoutRequest, CheckoutResponse
from app.services.checkout import AlreadyOwned, NotPurchasable, start_checkout
from app.services.freedompay import FreedomPayClient, FreedomPayError, get_gateway

router = APIRouter(tags=["checkout"])


@router.post("/checkout", response_model=CheckoutResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(CHECKOUT_RATE_LIMIT)
def create_checkout(
    request: Request,  # required by slowapi to key the limit
    body: CheckoutRequest,
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
    gateway: Annotated[FreedomPayClient, Depends(get_gateway)],
):
    course = session.get(Course, body.course_id)
    # Drafts 404 rather than 403 — same visibility rule the catalog uses, so
    # checkout can't be used to probe for unreleased courses.
    if course is None or course.status != CourseStatus.published:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )

    try:
        purchase, redirect_url = start_checkout(session, gateway, user, course)
    except AlreadyOwned:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="You already own this course"
        )
    except NotPurchasable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Course is not for sale"
        )
    except (FreedomPayError, httpx.HTTPError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Payment gateway unavailable"
        )

    return CheckoutResponse(
        purchase_id=purchase.id,
        payment_id=purchase.gateway_txn_id,
        redirect_url=redirect_url,
        amount=purchase.amount,
        currency=purchase.currency,
        status=purchase.status,
    )
