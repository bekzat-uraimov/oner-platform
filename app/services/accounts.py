"""Admin support work: finding an account, seeing what it owns and paid for,
and changing the parts of it an admin is allowed to change."""

from sqlmodel import Session, func, select

from app.core.security import hash_password
from app.models import Course, Entitlement, Purchase, PurchaseStatus, User, UserRole
from app.models.base import utcnow


class LastAdmin(Exception):
    """The change would leave no active admin, and then nobody could undo it."""


class NotRefundable(Exception):
    """Only a paid purchase took money, so only a paid purchase can be refunded."""


def _email_contains(column, text: str):
    # autoescape keeps % and _ in the search literal instead of wildcards.
    return func.lower(column).contains(text.lower(), autoescape=True)


def _page(session: Session, stmt, *, order_by, limit: int | None, offset: int):
    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
    stmt = stmt.order_by(*order_by).offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(session.exec(stmt).all()), total


def search_users(
    session: Session,
    *,
    email: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[User], int]:
    """Accounts whose email contains `email`, ignoring case, newest first."""
    stmt = select(User)
    if email:
        stmt = stmt.where(_email_contains(User.email, email))
    return _page(
        session,
        stmt,
        order_by=(User.created_at.desc(), User.id.desc()),
        limit=limit,
        offset=offset,
    )


def search_purchases(
    session: Session,
    *,
    email: str | None = None,
    user_id: int | None = None,
    course_id: int | None = None,
    status: PurchaseStatus | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[tuple[Purchase, str, str]], int]:
    """Payment attempts newest first, each with the buyer's email and the course
    title. Every status counts: pending is an abandoned checkout, failed is a
    declined payment."""
    stmt = (
        select(Purchase, User.email, Course.title)
        .join(User, User.id == Purchase.user_id)
        .join(Course, Course.id == Purchase.course_id)
    )
    if email:
        stmt = stmt.where(_email_contains(User.email, email))
    if user_id is not None:
        stmt = stmt.where(Purchase.user_id == user_id)
    if course_id is not None:
        stmt = stmt.where(Purchase.course_id == course_id)
    if status is not None:
        stmt = stmt.where(Purchase.status == status)
    return _page(
        session,
        stmt,
        order_by=(Purchase.created_at.desc(), Purchase.id.desc()),
        limit=limit,
        offset=offset,
    )


def owned_courses(session: Session, user_id: int) -> list[tuple[Entitlement, str]]:
    return list(
        session.exec(
            select(Entitlement, Course.title)
            .join(Course, Course.id == Entitlement.course_id)
            .where(Entitlement.user_id == user_id)
            .order_by(Entitlement.granted_at.desc(), Entitlement.id.desc())
        ).all()
    )


def _active_admins(session: Session) -> int:
    return session.exec(
        select(func.count())
        .select_from(User)
        .where(User.role == UserRole.admin, User.is_active.is_(True))
    ).one()


def update_user(session: Session, user: User, fields: dict) -> User:
    """Apply an admin's changes; a new password is hashed like any other.

    Refuses anything that would leave no active admin, because nobody could put
    that right through the API afterwards.
    """
    fields = dict(fields)
    password = fields.pop("password", None)

    was_admin = user.role == UserRole.admin and user.is_active
    stays_admin = fields.get("role", user.role) == UserRole.admin and fields.get(
        "is_active", user.is_active
    )
    if was_admin and not stays_admin and _active_admins(session) <= 1:
        raise LastAdmin(f"user {user.id} is the last active admin")

    for key, value in fields.items():
        setattr(user, key, value)
    if password is not None:
        user.password_hash = hash_password(password)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def refund_purchase(
    session: Session,
    purchase: Purchase,
    *,
    admin_id: int,
    revoke_access: bool,
    note: str | None = None,
) -> Purchase:
    """Record a refund already made in FreedomPay's merchant cabinet, and take
    the course away if the admin says so.

    Nothing here calls FreedomPay: their docs describe two different refund
    endpoints, and there are no sandbox credentials yet to find the real one.
    The refund and the revoke commit together, so neither happens alone.
    """
    if purchase.status != PurchaseStatus.paid:
        raise NotRefundable(f"purchase {purchase.id} is {purchase.status.value}")

    purchase.status = PurchaseStatus.refunded
    purchase.refunded_at = utcnow()
    purchase.refunded_by = admin_id
    purchase.refund_note = note
    session.add(purchase)
    if revoke_access:
        entitlement = session.exec(
            select(Entitlement).where(
                Entitlement.user_id == purchase.user_id,
                Entitlement.course_id == purchase.course_id,
            )
        ).first()
        if entitlement is not None:
            session.delete(entitlement)
    session.commit()
    session.refresh(purchase)
    return purchase
