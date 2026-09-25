"""Admin support routes: look up accounts and payments, change an account.

Kept apart from admin.py, which is about course content. Everything here is
still admin-only.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.api.deps import AdminUser
from app.core.db import get_session
from app.models import Purchase, PurchaseStatus, User
from app.schemas import (
    OwnedCourseAdmin,
    Page,
    PurchaseAdmin,
    RefundRequest,
    UserAdmin,
    UserAdminDetail,
    UserUpdate,
)
from app.services.accounts import (
    LastAdmin,
    NotRefundable,
    owned_courses,
    refund_purchase,
    search_purchases,
    search_users,
    update_user,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

SessionDep = Annotated[Session, Depends(get_session)]
EmailQuery = Annotated[str | None, Query(max_length=320)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def _user_or_404(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _purchase_row(row) -> PurchaseAdmin:
    purchase, email, title = row
    return PurchaseAdmin(
        id=purchase.id,
        user_id=purchase.user_id,
        user_email=email,
        course_id=purchase.course_id,
        course_title=title,
        gateway=purchase.gateway,
        gateway_txn_id=purchase.gateway_txn_id,
        amount=purchase.amount,
        currency=purchase.currency,
        status=purchase.status,
        created_at=purchase.created_at,
        refunded_at=purchase.refunded_at,
        refunded_by=purchase.refunded_by,
        refund_note=purchase.refund_note,
    )


@router.get("/users", response_model=Page[UserAdmin])
def find_users(
    _admin: AdminUser,
    session: SessionDep,
    email: EmailQuery = None,
    limit: Limit = 20,
    offset: Offset = 0,
):
    """Accounts whose email contains `email`, ignoring case, newest first."""
    users, total = search_users(session, email=email, limit=limit, offset=offset)
    return Page[UserAdmin](
        items=[UserAdmin.model_validate(user) for user in users], total=total
    )


@router.get("/users/{user_id}", response_model=UserAdminDetail)
def read_user(user_id: int, _admin: AdminUser, session: SessionDep):
    """An account with every course it owns and every payment it attempted."""
    user = _user_or_404(session, user_id)
    purchases, _ = search_purchases(session, user_id=user.id)
    return UserAdminDetail(
        **UserAdmin.model_validate(user).model_dump(),
        owned_courses=[
            OwnedCourseAdmin(
                course_id=entitlement.course_id,
                course_title=title,
                granted_at=entitlement.granted_at,
                source_purchase_id=entitlement.source_purchase_id,
            )
            for entitlement, title in owned_courses(session, user.id)
        ],
        purchases=[_purchase_row(row) for row in purchases],
    )


@router.patch("/users/{user_id}", response_model=UserAdmin)
def edit_user(user_id: int, body: UserUpdate, admin: AdminUser, session: SessionDep):
    user = _user_or_404(session, user_id)
    fields = body.model_dump(exclude_unset=True)
    try:
        user = update_user(session, user, fields)
    except LastAdmin:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That would leave no active admin",
        )
    # The audit trail: which admin changed which fields. Never the values, so a
    # new password doesn't end up in the logs.
    log.info(
        "admin %s changed %s on user %s", admin.id, ", ".join(sorted(fields)), user.id
    )
    return user


@router.get("/purchases", response_model=Page[PurchaseAdmin])
def find_purchases(
    _admin: AdminUser,
    session: SessionDep,
    email: EmailQuery = None,
    course_id: int | None = None,
    purchase_status: Annotated[PurchaseStatus | None, Query(alias="status")] = None,
    limit: Limit = 20,
    offset: Offset = 0,
):
    """Transaction history, newest first. Filter by part of the buyer's email,
    by course, or by status; pending rows are abandoned checkouts."""
    rows, total = search_purchases(
        session,
        email=email,
        course_id=course_id,
        status=purchase_status,
        limit=limit,
        offset=offset,
    )
    return Page[PurchaseAdmin](items=[_purchase_row(row) for row in rows], total=total)


@router.post("/purchases/{purchase_id}/refund", response_model=PurchaseAdmin)
def refund(purchase_id: int, body: RefundRequest, admin: AdminUser, session: SessionDep):
    """Record a refund made in FreedomPay's merchant cabinet. This sends no
    money: it marks the purchase refunded and, if asked, takes the course away."""
    purchase = session.get(Purchase, purchase_id)
    if purchase is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase not found")
    try:
        purchase = refund_purchase(
            session,
            purchase,
            admin_id=admin.id,
            revoke_access=body.revoke_access,
            note=body.note,
        )
    except NotRefundable:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only a paid purchase can be refunded; this one is {purchase.status.value}",
        )
    log.info(
        "admin %s refunded purchase %s, access %s",
        admin.id,
        purchase.id,
        "revoked" if body.revoke_access else "kept",
    )
    return _purchase_row((purchase, purchase.user.email, purchase.course.title))
