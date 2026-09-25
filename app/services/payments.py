"""Settling a FreedomPay result callback — the only path that turns money into
access.

Every rule here exists because the caller is the open internet. The signature
says the message came from FreedomPay; the amount and order checks say it
describes a purchase we actually created; the status check says we haven't
already acted on it. Nothing is taken on trust, including the amount.
"""

import logging
from decimal import Decimal, InvalidOperation

from sqlmodel import Session, select

from app.models import Entitlement, Purchase, PurchaseStatus
from app.services.entitlements import grant
from app.services.freedompay import (
    RESULT_FAILED,
    RESULT_PAID,
    FreedomPayClient,
    script_name,
    verify_sig,
)


log = logging.getLogger("oner.payments")


class ResultRejected(Exception):
    """The callback can't be acted on, and retrying it won't change that."""


class PaymentRefused(Exception):
    """A second payment for a course the buyer already paid for, which
    FreedomPay offered to cancel (pg_can_reject=1)."""


def _amount(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def _purchase(session: Session, raw_order_id: str | None) -> Purchase | None:
    if raw_order_id is None or not raw_order_id.isdigit():
        return None
    return session.get(Purchase, int(raw_order_id))


def _paid_through_another_order(session: Session, purchase: Purchase) -> bool:
    entitlement = session.exec(
        select(Entitlement).where(
            Entitlement.user_id == purchase.user_id,
            Entitlement.course_id == purchase.course_id,
        )
    ).first()
    # A manual grant (no source) isn't a payment, so paying after one is fine.
    return entitlement is not None and entitlement.source_purchase_id not in (
        None,
        purchase.id,
    )


def _second_payment(params: dict[str, str], payment_id: str, reason: str) -> None:
    """Cancel a duplicate charge when FreedomPay allows it. Otherwise the money
    is taken regardless of our answer, and only a refund in the merchant
    cabinet can return it, so say so where someone will look."""
    if params.get("pg_can_reject") == "1":
        raise PaymentRefused(f"{reason}; rejecting payment {payment_id}")
    log.warning(
        "%s; payment %s was taken anyway, refund it in the merchant cabinet",
        reason,
        payment_id,
    )


def settle_payment(
    session: Session, gateway: FreedomPayClient, params: dict[str, str]
) -> Purchase:
    """Apply a result callback. Idempotent: replays return without re-granting."""
    if not verify_sig(script_name(gateway.result_url), params, gateway.secret_key):
        raise ResultRejected("signature mismatch")

    # A sandbox ping must never unlock content on a live merchant account.
    if gateway.testing_mode == 0 and params.get("pg_testing_mode") == "1":
        raise ResultRejected("test callback on a live merchant")

    purchase = _purchase(session, params.get("pg_order_id"))
    if purchase is None:
        raise ResultRejected(f"unknown order {params.get('pg_order_id')!r}")

    payment_id = params.get("pg_payment_id")

    # FreedomPay retries every 30 min for 2 hours until we answer 200, so the
    # same settled payment will arrive more than once. A refunded one too, and a
    # late retry must not hand the course back. A different payment id is no
    # retry, though: the buyer paid a second link for an order already settled.
    if purchase.status in (PurchaseStatus.paid, PurchaseStatus.refunded):
        if (
            params.get("pg_result") == RESULT_PAID
            and payment_id
            and payment_id != purchase.gateway_txn_id
        ):
            _second_payment(
                params, payment_id, f"order {purchase.id} is already {purchase.status.value}"
            )
        return purchase

    # The amount is theirs to report and ours to distrust — a replayed callback
    # claiming a smaller sum must not unlock the course.
    if _amount(params.get("pg_amount")) != purchase.amount:
        raise ResultRejected(f"amount mismatch on order {purchase.id}")
    if params.get("pg_currency") != purchase.currency.value:
        raise ResultRejected(f"currency mismatch on order {purchase.id}")

    result = params.get("pg_result")
    if result == RESULT_FAILED:
        purchase.status = PurchaseStatus.failed
        session.add(purchase)
        session.commit()
        session.refresh(purchase)
        return purchase

    if result != RESULT_PAID:
        # 2 = not completed. Nothing decided yet; a later callback will say.
        return purchase

    # pg_auto_clearing=1 should capture on the spot, so an explicit 0 here means
    # the money is authorized but not taken. Absent means the payment method
    # doesn't report capture at all, which is not a reason to withhold access.
    if params.get("pg_captured") == "0":
        raise ResultRejected(f"payment authorized but not captured on order {purchase.id}")

    if not payment_id:
        raise ResultRejected(f"paid callback with no payment id on order {purchase.id}")

    # Two open orders for one course (links from before and after a price
    # change) can both be paid, and the second pays for nothing.
    if _paid_through_another_order(session, purchase):
        _second_payment(
            params,
            payment_id,
            f"user {purchase.user_id} already paid for course {purchase.course_id} "
            f"with another order than {purchase.id}",
        )

    # Grant before marking paid. Both steps are idempotent, so a crash in
    # between leaves a retry able to finish the job — whereas a purchase marked
    # paid with no entitlement is a customer who paid and got nothing.
    grant(
        session,
        purchase.user_id,
        purchase.course_id,
        source_purchase_id=purchase.id,
    )

    # The id that actually settled, which is not necessarily the one from the
    # most recent checkout if the buyer paid an older link.
    purchase.gateway_txn_id = payment_id
    purchase.status = PurchaseStatus.paid
    session.add(purchase)
    session.commit()
    session.refresh(purchase)
    return purchase
