"""Day 7 — the pay→access path. A verified callback grants exactly once.

The callback is unauthenticated and arrives from the open internet, so most of
these tests are about what must NOT unlock a course.
"""

import logging
from decimal import Decimal
from xml.etree import ElementTree

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.security import create_access_token, hash_password
from app.models import (
    Course,
    CourseStatus,
    Currency,
    Entitlement,
    Purchase,
    PurchaseStatus,
    User,
)
from app.services.entitlements import grant
from app.services.freedompay import build_response, make_sig, verify_sig
from tests.conftest import TEST_RESULT_URL, TEST_SECRET

RESULT_PATH = "/webhooks/freedompay/result"
SCRIPT = "result"


# ---- helpers --------------------------------------------------------------

def _user(session: Session, email: str = "buyer@oner.kg") -> User:
    user = User(email=email, password_hash=hash_password("supersecret123"))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _course(session: Session, slug: str = "python-basics") -> Course:
    course = Course(
        title=slug.title(),
        slug=slug,
        price=Decimal("2500.00"),
        currency=Currency.KGS,
        status=CourseStatus.published,
    )
    session.add(course)
    session.commit()
    session.refresh(course)
    return course


def _pending(session: Session, user: User, course: Course) -> Purchase:
    purchase = Purchase(
        user_id=user.id,
        course_id=course.id,
        amount=course.price,
        currency=course.currency,
        gateway_txn_id="pg-payment-1",
    )
    session.add(purchase)
    session.commit()
    session.refresh(purchase)
    return purchase


def _callback(purchase: Purchase, **overrides) -> dict[str, str]:
    """A well-formed successful result callback, signed like FreedomPay would."""
    params = {
        "pg_order_id": str(purchase.id),
        "pg_payment_id": "pg-payment-1",
        "pg_amount": f"{purchase.amount:.2f}",
        "pg_currency": purchase.currency.value,
        "pg_result": "1",
        "pg_payment_method": "bankcard",
        "pg_salt": "abc123",
        "pg_testing_mode": "1",
    }
    params.update(overrides)
    params = {k: v for k, v in params.items() if v is not None}
    params["pg_sig"] = make_sig(SCRIPT, params, TEST_SECRET)
    return params


def _status(res) -> str:
    return ElementTree.fromstring(res.text).findtext("pg_status")


def _owns(session: Session, user: User, course: Course) -> bool:
    return (
        session.exec(
            select(Entitlement).where(
                Entitlement.user_id == user.id, Entitlement.course_id == course.id
            )
        ).first()
        is not None
    )


@pytest.fixture
def purchase(session: Session) -> Purchase:
    return _pending(session, _user(session), _course(session))


# ---- the happy path -------------------------------------------------------

def test_paid_callback_grants_access_and_marks_the_purchase_paid(
    client: TestClient, session: Session, purchase: Purchase
):
    res = client.post(RESULT_PATH, data=_callback(purchase))

    assert res.status_code == 200
    assert _status(res) == "ok"

    session.refresh(purchase)
    assert purchase.status == PurchaseStatus.paid
    entitlement = session.exec(select(Entitlement)).one()
    assert entitlement.user_id == purchase.user_id
    assert entitlement.course_id == purchase.course_id
    assert entitlement.source_purchase_id == purchase.id


def test_checkout_then_callback_puts_the_course_in_my_courses(
    client: TestClient, session: Session
):
    user = _user(session)
    course = _course(session)
    headers = {"Authorization": f"Bearer {create_access_token(user.id)}"}

    assert client.get("/me/courses", headers=headers).json() == []

    checkout = client.post(
        "/checkout", json={"course_id": course.id}, headers=headers
    ).json()
    purchase = session.get(Purchase, checkout["purchase_id"])
    client.post(RESULT_PATH, data=_callback(purchase))

    owned = client.get("/me/courses", headers=headers).json()
    assert [c["slug"] for c in owned] == [course.slug]


def test_our_reply_is_signed_so_freedompay_can_verify_it(
    client: TestClient, purchase: Purchase
):
    res = client.post(RESULT_PATH, data=_callback(purchase))

    fields = {el.tag: el.text for el in ElementTree.fromstring(res.text)}
    assert verify_sig(SCRIPT, fields, TEST_SECRET)


# ---- replays --------------------------------------------------------------

def test_replayed_callback_does_not_grant_twice(
    client: TestClient, session: Session, purchase: Purchase
):
    body = _callback(purchase)

    first = client.post(RESULT_PATH, data=body)
    second = client.post(RESULT_PATH, data=body)

    assert _status(first) == _status(second) == "ok"
    assert len(session.exec(select(Entitlement)).all()) == 1


def test_replay_with_a_lowered_amount_cannot_touch_a_settled_purchase(
    client: TestClient, session: Session, purchase: Purchase
):
    client.post(RESULT_PATH, data=_callback(purchase))

    res = client.post(RESULT_PATH, data=_callback(purchase, pg_amount="1.00"))

    # Already paid, so it short-circuits before the amount check and stays paid.
    assert _status(res) == "ok"
    session.refresh(purchase)
    assert purchase.amount == Decimal("2500.00")
    assert len(session.exec(select(Entitlement)).all()) == 1


# ---- everything that must not grant ---------------------------------------

def test_forged_signature_grants_nothing(
    client: TestClient, session: Session, purchase: Purchase
):
    body = _callback(purchase) | {"pg_sig": "0" * 32}

    res = client.post(RESULT_PATH, data=body)

    assert res.status_code == 200
    assert _status(res) == "error"
    assert session.exec(select(Entitlement)).all() == []
    session.refresh(purchase)
    assert purchase.status == PurchaseStatus.pending


def test_tampering_with_the_amount_breaks_the_signature(
    client: TestClient, session: Session, purchase: Purchase
):
    body = _callback(purchase)
    body["pg_amount"] = "1.00"  # signed for 2500.00

    res = client.post(RESULT_PATH, data=body)

    assert _status(res) == "error"
    assert session.exec(select(Entitlement)).all() == []


def test_correctly_signed_but_wrong_amount_is_rejected(
    client: TestClient, session: Session, purchase: Purchase
):
    # Signature valid, amount simply doesn't match what we're owed.
    res = client.post(RESULT_PATH, data=_callback(purchase, pg_amount="1.00"))

    assert _status(res) == "error"
    assert session.exec(select(Entitlement)).all() == []
    session.refresh(purchase)
    assert purchase.status == PurchaseStatus.pending


def test_wrong_currency_is_rejected(
    client: TestClient, session: Session, purchase: Purchase
):
    res = client.post(RESULT_PATH, data=_callback(purchase, pg_currency="USD"))

    assert _status(res) == "error"
    assert session.exec(select(Entitlement)).all() == []


def test_unknown_order_is_rejected(client: TestClient, session: Session):
    fake = Purchase(user_id=1, course_id=1, amount=Decimal("10.00"))
    fake.id = 9999

    res = client.post(RESULT_PATH, data=_callback(fake))

    assert _status(res) == "error"
    assert session.exec(select(Entitlement)).all() == []


def test_non_numeric_order_id_is_rejected(client: TestClient, purchase: Purchase):
    res = client.post(RESULT_PATH, data=_callback(purchase, pg_order_id="../../etc"))

    assert _status(res) == "error"


def test_failed_payment_marks_the_purchase_failed_without_granting(
    client: TestClient, session: Session, purchase: Purchase
):
    res = client.post(RESULT_PATH, data=_callback(purchase, pg_result="0"))

    assert _status(res) == "ok"
    session.refresh(purchase)
    assert purchase.status == PurchaseStatus.failed
    assert session.exec(select(Entitlement)).all() == []


def test_incomplete_payment_leaves_the_purchase_pending(
    client: TestClient, session: Session, purchase: Purchase
):
    res = client.post(RESULT_PATH, data=_callback(purchase, pg_result="2"))

    assert _status(res) == "ok"
    session.refresh(purchase)
    assert purchase.status == PurchaseStatus.pending
    assert session.exec(select(Entitlement)).all() == []


def test_paid_callback_without_a_payment_id_is_rejected(
    client: TestClient, session: Session, purchase: Purchase
):
    res = client.post(RESULT_PATH, data=_callback(purchase, pg_payment_id=None))

    assert _status(res) == "error"
    assert session.exec(select(Entitlement)).all() == []


def test_authorized_but_uncaptured_payment_is_rejected(
    client: TestClient, session: Session, purchase: Purchase
):
    # pg_auto_clearing=1 should capture immediately; an explicit 0 means the card
    # was only authorized and the money isn't ours yet.
    res = client.post(RESULT_PATH, data=_callback(purchase, pg_captured="0"))

    assert _status(res) == "error"
    assert session.exec(select(Entitlement)).all() == []
    session.refresh(purchase)
    assert purchase.status == PurchaseStatus.pending


def test_missing_pg_captured_still_grants(
    client: TestClient, session: Session, purchase: Purchase
):
    # Not every payment method reports capture; absence must not block access.
    res = client.post(RESULT_PATH, data=_callback(purchase))

    assert _status(res) == "ok"
    assert len(session.exec(select(Entitlement)).all()) == 1


def test_sandbox_callback_is_rejected_on_a_live_merchant(
    client: TestClient, session: Session, purchase: Purchase, gateway
):
    gateway.testing_mode = 0

    res = client.post(RESULT_PATH, data=_callback(purchase, pg_testing_mode="1"))

    assert _status(res) == "error"
    assert session.exec(select(Entitlement)).all() == []


# ---- paying twice -----------------------------------------------------------

def _second_order(session: Session, first: Purchase, amount: str = "3000.00") -> Purchase:
    """Another open order for the same buyer and course, e.g. from after a price change."""
    order = Purchase(
        user_id=first.user_id,
        course_id=first.course_id,
        amount=Decimal(amount),
        currency=first.currency,
        gateway_txn_id="pg-payment-2",
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


def test_a_second_payment_on_a_settled_order_is_rejected_when_freedompay_allows(
    client: TestClient, session: Session, purchase: Purchase
):
    client.post(RESULT_PATH, data=_callback(purchase))

    res = client.post(
        RESULT_PATH, data=_callback(purchase, pg_payment_id="pg-payment-2", pg_can_reject="1")
    )

    assert _status(res) == "rejected"
    # FreedomPay shows this to the buyer, then sends them to the failure page.
    assert ElementTree.fromstring(res.text).findtext("pg_description")
    session.refresh(purchase)
    assert (purchase.status, purchase.gateway_txn_id) == (PurchaseStatus.paid, "pg-payment-1")


def test_a_second_payment_that_cannot_be_rejected_is_accepted_and_flagged(
    client: TestClient, session: Session, purchase: Purchase, caplog
):
    client.post(RESULT_PATH, data=_callback(purchase))
    caplog.set_level(logging.WARNING, logger="oner.payments")

    res = client.post(RESULT_PATH, data=_callback(purchase, pg_payment_id="pg-payment-2"))

    assert _status(res) == "ok"
    assert "pg-payment-2" in caplog.text and "refund it" in caplog.text


def test_a_retry_of_the_settled_payment_is_not_a_second_payment(
    client: TestClient, session: Session, purchase: Purchase
):
    client.post(RESULT_PATH, data=_callback(purchase))

    res = client.post(RESULT_PATH, data=_callback(purchase, pg_can_reject="1"))

    assert _status(res) == "ok"


def test_paying_a_second_order_for_an_owned_course_is_rejected(
    client: TestClient, session: Session, purchase: Purchase
):
    client.post(RESULT_PATH, data=_callback(purchase))
    second = _second_order(session, purchase)

    res = client.post(
        RESULT_PATH, data=_callback(second, pg_payment_id="pg-payment-2", pg_can_reject="1")
    )

    assert _status(res) == "rejected"
    session.refresh(second)
    assert second.status == PurchaseStatus.pending


def test_a_second_order_that_cannot_be_rejected_is_recorded_as_paid_and_flagged(
    client: TestClient, session: Session, purchase: Purchase, caplog
):
    client.post(RESULT_PATH, data=_callback(purchase))
    second = _second_order(session, purchase)
    caplog.set_level(logging.WARNING, logger="oner.payments")

    res = client.post(RESULT_PATH, data=_callback(second, pg_payment_id="pg-payment-2"))

    assert _status(res) == "ok"
    session.refresh(second)
    assert second.status == PurchaseStatus.paid  # the money was taken; the record says so
    assert "refund it" in caplog.text


def test_paying_after_a_manual_grant_is_not_a_duplicate(
    client: TestClient, session: Session, purchase: Purchase
):
    grant(session, purchase.user_id, purchase.course_id)

    res = client.post(RESULT_PATH, data=_callback(purchase, pg_can_reject="1"))

    assert _status(res) == "ok"
    session.refresh(purchase)
    assert purchase.status == PurchaseStatus.paid


def test_a_rejection_reason_goes_where_freedompay_shows_it_to_the_buyer():
    root = ElementTree.fromstring(
        build_response("result", TEST_SECRET, status="rejected", description="already paid")
    )

    assert root.findtext("pg_description") == "already paid"
    assert root.findtext("pg_error_description") is None


# ---- protocol details -----------------------------------------------------

def test_unknown_extra_fields_still_verify(
    client: TestClient, session: Session, purchase: Purchase
):
    # FreedomPay signs every field it sends, including ones we've never seen.
    # Parsing into a fixed schema would drop them and break verification.
    res = client.post(
        RESULT_PATH, data=_callback(purchase, pg_some_future_field="whatever")
    )

    assert _status(res) == "ok"
    assert len(session.exec(select(Entitlement)).all()) == 1


def test_the_signature_is_bound_to_the_result_url_segment(purchase: Purchase):
    body = _callback(purchase)

    # Same fields signed as if they were an init_payment call: must not verify.
    assert not verify_sig("init_payment.php", body, TEST_SECRET)
    assert verify_sig("result", body, TEST_SECRET)
    assert TEST_RESULT_URL.endswith("/result")


def test_rejections_still_answer_200_so_the_reply_is_readable(
    client: TestClient, purchase: Purchase
):
    res = client.post(RESULT_PATH, data={"pg_order_id": str(purchase.id)})

    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/xml")
    assert _status(res) == "error"


def test_oversized_callback_is_refused_before_parsing(
    client: TestClient, purchase: Purchase
):
    # Unauthenticated endpoint, and form bodies are buffered in memory.
    body = _callback(purchase) | {"pg_description": "x" * 70_000}

    res = client.post(RESULT_PATH, data=body)

    assert res.status_code == 413
