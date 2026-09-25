"""Checkout: turn a course into a pending Purchase plus a gateway payment link.

Nothing here grants access. The purchase stays `pending` until FreedomPay's
server-to-server result callback verifies it (Day 7). Granting on the browser
redirect instead would be free piracy.
"""

from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models import Course, Currency, Purchase, PurchaseStatus, User
from app.services.entitlements import has_access
from app.services.freedompay import FreedomPayClient


class AlreadyOwned(Exception):
    """The user already has an entitlement for this course."""


class NotPurchasable(Exception):
    """The course exists but can't be sold as-is (no price)."""


def pending_purchase(
    session: Session, user_id: int, course_id: int, amount: Decimal, currency: Currency
) -> Purchase | None:
    """The buyer's open order for this course at this price, if there is one."""
    return session.exec(
        select(Purchase).where(
            Purchase.user_id == user_id,
            Purchase.course_id == course_id,
            Purchase.amount == amount,
            Purchase.currency == currency,
            Purchase.status == PurchaseStatus.pending,
        )
    ).first()


def _open_order(session: Session, user: User, course: Course) -> Purchase:
    purchase = Purchase(
        user_id=user.id,
        course_id=course.id,
        amount=course.price,
        currency=course.currency,
    )
    session.add(purchase)
    try:
        session.commit()
    except IntegrityError:
        # A simultaneous click opened this order first (uq_pending_purchase).
        session.rollback()
        won = pending_purchase(session, user.id, course.id, course.price, course.currency)
        assert won is not None  # the index fired, so the row exists
        return won
    session.refresh(purchase)
    return purchase


def start_checkout(
    session: Session,
    gateway: FreedomPayClient,
    user: User,
    course: Course,
) -> tuple[Purchase, str]:
    """Open or reuse a pending order and return it with a payment URL."""
    if course.price <= 0:
        raise NotPurchasable(f"course {course.id} has no price")
    if has_access(session, user.id, course.id):
        raise AlreadyOwned(f"user {user.id} already owns course {course.id}")

    # Clicking Buy twice reuses the open order, which keeps pg_order_id stable
    # for the webhook. Only an order at today's price is reused: a link from
    # before a price change can still be paid, and its callback has to match
    # the amount that link asked for.
    purchase = pending_purchase(
        session, user.id, course.id, course.price, course.currency
    ) or _open_order(session, user, course)

    init = gateway.init_payment(
        order_id=purchase.id,
        amount=purchase.amount,
        currency=purchase.currency.value,
        description=f"ONER — {course.title}",
    )

    purchase.gateway_txn_id = init.payment_id
    session.add(purchase)
    session.commit()
    session.refresh(purchase)
    return purchase, init.redirect_url
