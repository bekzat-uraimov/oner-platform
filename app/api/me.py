"""Routes scoped to the authenticated user."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.api.deps import CurrentUser
from app.core.db import get_session
from app.models import Purchase
from app.schemas import CourseListItem, MyPurchase
from app.services.entitlements import list_owned_courses

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/courses", response_model=list[CourseListItem])
def my_courses(
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
):
    """Courses the current user owns (has an entitlement for)."""
    return list_owned_courses(session, user.id)


@router.get("/purchases/{purchase_id}", response_model=MyPurchase)
def my_purchase(
    purchase_id: int,
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
):
    """One of the user's own orders, so the checkout return page can tell a
    confirmed payment from a pending or failed one. Someone else's order is a
    404, so ids can't be probed."""
    purchase = session.get(Purchase, purchase_id)
    if purchase is None or purchase.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Purchase not found"
        )
    return purchase
