"""The access core. A row in `entitlements` is the ONLY thing that means a user
owns a course. Every gate in the app routes through has_access().

grant() is idempotent on purpose: payment webhooks retry, so granting the same
(user, course) twice must never create a second row or raise.
"""

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models import Course, Entitlement, User, UserRole


def has_access(session: Session, user_id: int, course_id: int) -> bool:
    row = session.exec(
        select(Entitlement.id).where(
            Entitlement.user_id == user_id,
            Entitlement.course_id == course_id,
        )
    ).first()
    return row is not None


def can_access_course(session: Session, user: User, course_id: int) -> bool:
    """Admins see everything; everyone else needs an entitlement."""
    return user.role == UserRole.admin or has_access(session, user.id, course_id)


def _find(session: Session, user_id: int, course_id: int) -> Entitlement | None:
    return session.exec(
        select(Entitlement).where(
            Entitlement.user_id == user_id,
            Entitlement.course_id == course_id,
        )
    ).first()


def grant(
    session: Session,
    user_id: int,
    course_id: int,
    *,
    source_purchase_id: int | None = None,
) -> Entitlement:
    """Grant access to (user, course). Returns the existing row if already granted.

    The unique (user_id, course_id) constraint is the backstop: if two concurrent
    grants race past the existence check, the second hits IntegrityError and we
    return the row that won.
    """
    existing = _find(session, user_id, course_id)
    if existing is not None:
        return existing

    entitlement = Entitlement(
        user_id=user_id,
        course_id=course_id,
        source_purchase_id=source_purchase_id,
    )
    session.add(entitlement)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        won = _find(session, user_id, course_id)
        assert won is not None  # the constraint fired, so a row must exist
        return won
    session.refresh(entitlement)
    return entitlement


def revoke(session: Session, user_id: int, course_id: int) -> bool:
    """Take a course away. False if the user didn't own it."""
    entitlement = _find(session, user_id, course_id)
    if entitlement is None:
        return False
    session.delete(entitlement)
    session.commit()
    return True


def list_owned_courses(session: Session, user_id: int) -> list[Course]:
    stmt = (
        select(Course)
        .join(Entitlement, Entitlement.course_id == Course.id)
        .where(Entitlement.user_id == user_id)
    )
    return list(session.exec(stmt).all())
