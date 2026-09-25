"""Refunds and taking a course away.

The money goes back through FreedomPay's merchant cabinet; the API records it
and, if the admin says so, removes access. A refund has to stick: FreedomPay
keeps retrying the original paid callback, and none of those can hand the
course back.
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.security import create_access_token, hash_password
from app.models import Course, CourseStatus, Currency, Purchase, PurchaseStatus, User, UserRole
from app.services.entitlements import grant, has_access
from tests.test_webhooks import RESULT_PATH, _callback, _status

# Not the fake gateway's pg-payment-N, which a later checkout would reuse.
PAYMENT_ID = "pg-original"


def _user(session: Session, email: str, role: UserRole = UserRole.student) -> User:
    user = User(email=email, password_hash=hash_password("supersecret123"), role=role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def _purchase(session: Session, buyer: User, course: Course, status: PurchaseStatus) -> Purchase:
    purchase = Purchase(
        user_id=buyer.id,
        course_id=course.id,
        amount=course.price,
        currency=course.currency,
        status=status,
    )
    session.add(purchase)
    session.commit()
    session.refresh(purchase)
    return purchase


def _refund(client: TestClient, headers: dict, purchase: Purchase, **body):
    return client.post(
        f"/admin/purchases/{purchase.id}/refund",
        json={"revoke_access": True, **body},
        headers=headers,
    )


def _revoke(client: TestClient, headers: dict, user: User, course: Course):
    return client.delete(
        "/admin/entitlements",
        params={"user_id": user.id, "course_id": course.id},
        headers=headers,
    )


@pytest.fixture
def admin(session: Session) -> User:
    return _user(session, "admin@oner.kg", UserRole.admin)


@pytest.fixture
def headers(admin: User) -> dict:
    return _auth(admin)


@pytest.fixture
def buyer(session: Session) -> User:
    return _user(session, "buyer@oner.kg")


@pytest.fixture
def course(session: Session) -> Course:
    course = Course(
        title="Python Basics",
        slug="python-basics",
        price=Decimal("2500.00"),
        currency=Currency.KGS,
        status=CourseStatus.published,
    )
    session.add(course)
    session.commit()
    session.refresh(course)
    return course


@pytest.fixture
def paid(client: TestClient, session: Session, buyer: User, course: Course) -> Purchase:
    """Bought through the real callback, so access comes from the payment."""
    purchase = _purchase(session, buyer, course, PurchaseStatus.pending)
    client.post(RESULT_PATH, data=_callback(purchase, pg_payment_id=PAYMENT_ID))
    session.refresh(purchase)
    assert purchase.status == PurchaseStatus.paid
    return purchase


# ---- refunds ---------------------------------------------------------------

def test_a_refund_that_revokes_access_takes_the_course_away(
    client: TestClient, session: Session, headers: dict, admin: User, buyer: User, course: Course, paid: Purchase
):
    res = _refund(client, headers, paid, note="Returned in the cabinet, ticket 42")

    assert res.status_code == 200
    body = res.json()
    assert (body["status"], body["refunded_by"], body["refund_note"]) == (
        "refunded",
        admin.id,
        "Returned in the cabinet, ticket 42",
    )
    assert body["refunded_at"] is not None
    assert not has_access(session, buyer.id, course.id)


def test_a_refund_can_leave_the_course_with_the_student(
    client: TestClient, session: Session, headers: dict, buyer: User, course: Course, paid: Purchase
):
    res = _refund(client, headers, paid, revoke_access=False)

    assert res.json()["status"] == "refunded"
    assert has_access(session, buyer.id, course.id)


def test_a_late_paid_callback_cannot_undo_a_refund(
    client: TestClient, session: Session, headers: dict, buyer: User, course: Course, paid: Purchase
):
    _refund(client, headers, paid)

    res = client.post(RESULT_PATH, data=_callback(paid, pg_payment_id=PAYMENT_ID))

    assert _status(res) == "ok"  # answered, so FreedomPay stops retrying
    session.refresh(paid)
    assert paid.status == PurchaseStatus.refunded
    assert not has_access(session, buyer.id, course.id)


@pytest.mark.parametrize("status", [PurchaseStatus.pending, PurchaseStatus.failed])
def test_only_a_paid_purchase_can_be_refunded(
    client: TestClient, session: Session, headers: dict, buyer: User, course: Course, status: PurchaseStatus
):
    purchase = _purchase(session, buyer, course, status)

    res = _refund(client, headers, purchase)

    assert res.status_code == 409
    assert status.value in res.json()["detail"]
    session.refresh(purchase)
    assert purchase.status == status


def test_a_purchase_is_refunded_only_once(
    client: TestClient, session: Session, headers: dict, paid: Purchase
):
    first = _refund(client, headers, paid, note="first").json()

    res = _refund(client, headers, paid, note="second")

    assert res.status_code == 409
    session.refresh(paid)
    assert paid.refund_note == "first"
    assert paid.refunded_at.isoformat().startswith(first["refunded_at"][:19])


def test_the_admin_has_to_say_whether_access_goes(
    client: TestClient, session: Session, headers: dict, buyer: User, course: Course, paid: Purchase
):
    res = client.post(f"/admin/purchases/{paid.id}/refund", json={}, headers=headers)

    assert res.status_code == 422
    session.refresh(paid)
    assert paid.status == PurchaseStatus.paid
    assert has_access(session, buyer.id, course.id)


def test_a_long_note_is_rejected(client: TestClient, headers: dict, paid: Purchase):
    assert _refund(client, headers, paid, note="x" * 501).status_code == 422


def test_refunding_an_unknown_purchase_is_404(client: TestClient, headers: dict):
    res = client.post("/admin/purchases/999/refund", json={"revoke_access": True}, headers=headers)

    assert res.status_code == 404


def test_students_cannot_refund(client: TestClient, buyer: User, paid: Purchase):
    assert _refund(client, _auth(buyer), paid).status_code == 403


def test_a_refund_shows_in_the_history_and_on_the_account(
    client: TestClient, headers: dict, buyer: User, paid: Purchase
):
    _refund(client, headers, paid, note="duplicate charge")

    history = client.get("/admin/purchases", params={"status": "refunded"}, headers=headers).json()
    account = client.get(f"/admin/users/{buyer.id}", headers=headers).json()

    assert [p["refund_note"] for p in history["items"]] == ["duplicate charge"]
    assert account["owned_courses"] == []
    assert [p["status"] for p in account["purchases"]] == ["refunded"]


def test_a_student_whose_refund_took_the_course_can_buy_it_again(
    client: TestClient, headers: dict, buyer: User, course: Course, paid: Purchase
):
    _refund(client, headers, paid)

    res = client.post("/checkout", json={"course_id": course.id}, headers=_auth(buyer))

    assert res.status_code == 201


# ---- revoking --------------------------------------------------------------

def test_an_admin_revokes_a_manual_grant(
    client: TestClient, session: Session, headers: dict, buyer: User, course: Course
):
    grant(session, buyer.id, course.id)

    res = _revoke(client, headers, buyer, course)

    assert res.status_code == 204
    assert not has_access(session, buyer.id, course.id)


def test_access_kept_after_a_refund_can_be_revoked_later(
    client: TestClient, session: Session, headers: dict, buyer: User, course: Course, paid: Purchase
):
    _refund(client, headers, paid, revoke_access=False)

    assert _revoke(client, headers, buyer, course).status_code == 204
    assert not has_access(session, buyer.id, course.id)
    session.refresh(paid)
    assert paid.status == PurchaseStatus.refunded


def test_revoking_a_course_the_user_does_not_own_is_404(
    client: TestClient, headers: dict, buyer: User, course: Course
):
    assert _revoke(client, headers, buyer, course).status_code == 404


def test_students_cannot_revoke(
    client: TestClient, session: Session, buyer: User, course: Course
):
    grant(session, buyer.id, course.id)

    assert _revoke(client, _auth(buyer), buyer, course).status_code == 403
    assert has_access(session, buyer.id, course.id)
