"""Day 6 — checkout produces a payment link and a pending purchase, nothing more.

Access is still not granted anywhere here; that's the Day 7 webhook's job.
"""

import hashlib
from decimal import Decimal
from urllib.parse import parse_qsl

import httpx
import pytest

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.security import create_access_token, hash_password
from app.services import checkout as checkout_service
from app.models import (
    Course,
    CourseStatus,
    Currency,
    Entitlement,
    Purchase,
    PurchaseStatus,
    User,
)
from app.services.freedompay import (
    MAX_DESCRIPTION,
    FreedomPayClient,
    FreedomPayError,
    PaymentInit,
    parse_init,
    make_sig,
    script_name,
    verify_sig,
)


# ---- fixtures / helpers ---------------------------------------------------

def _user(session: Session, email: str = "buyer@oner.kg") -> User:
    user = User(email=email, password_hash=hash_password("supersecret123"))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _course(
    session: Session,
    slug: str = "python-basics",
    *,
    price: str = "2500.00",
    status: CourseStatus = CourseStatus.published,
) -> Course:
    course = Course(
        title=slug.title(),
        slug=slug,
        price=Decimal(price),
        currency=Currency.KGS,
        status=status,
    )
    session.add(course)
    session.commit()
    session.refresh(course)
    return course


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


# ---- signature ------------------------------------------------------------

def test_sig_joins_script_then_sorted_values_then_secret():
    params = {"pg_order_id": "7", "pg_amount": "100.00", "pg_merchant_id": "m1"}

    # Sorted by key: pg_amount, pg_merchant_id, pg_order_id
    expected = hashlib.md5(
        b"init_payment.php;100.00;m1;7;secret"
    ).hexdigest()

    assert make_sig("init_payment.php", params, "secret") == expected


def test_sig_ignores_any_pg_sig_already_present():
    params = {"pg_order_id": "7"}
    with_sig = params | {"pg_sig": "stale"}

    assert make_sig("x.php", with_sig, "s") == make_sig("x.php", params, "s")


def test_verify_sig_accepts_own_signature():
    params = {"pg_order_id": "7", "pg_amount": "100.00"}
    params["pg_sig"] = make_sig("result", params, "secret")

    assert verify_sig("result", params, "secret")


def test_verify_sig_rejects_tampered_amount():
    params = {"pg_order_id": "7", "pg_amount": "100.00"}
    params["pg_sig"] = make_sig("result", params, "secret")
    params["pg_amount"] = "1.00"

    assert not verify_sig("result", params, "secret")


def test_verify_sig_rejects_missing_signature():
    assert not verify_sig("result", {"pg_order_id": "7"}, "secret")


def test_script_name_is_the_last_path_segment():
    assert script_name("https://api.freedompay.kg/init_payment.php") == "init_payment.php"
    assert script_name("https://oner.kg/webhooks/freedompay/result") == "result"


# ---- outgoing request -----------------------------------------------------

def _gateway(**overrides) -> FreedomPayClient:
    kwargs = {
        "merchant_id": "m1",
        "secret_key": "secret",
        "init_url": "https://api.freedompay.kg/init_payment.php",
        "result_url": "https://oner.kg/webhooks/freedompay/result",
        "success_url": "https://oner.kg/checkout/success",
        "failure_url": "https://oner.kg/checkout/failure",
        "testing_mode": 1,
        "timeout": 5.0,
    }
    return FreedomPayClient(**(kwargs | overrides))


def _stub_transport(gw: FreedomPayClient, seen: dict) -> None:
    """Point the client at an in-memory transport that records the form it sent."""

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(parse_qsl(request.content.decode()))
        return httpx.Response(
            200,
            text=(
                "<response><pg_status>ok</pg_status>"
                "<pg_payment_id>901</pg_payment_id>"
                "<pg_redirect_url>https://pay.kg/901</pg_redirect_url></response>"
            ),
        )

    gw.http = httpx.Client(transport=httpx.MockTransport(handler))


def test_init_payment_sends_a_form_that_validates_under_its_own_signature():
    seen = {}
    gw = _gateway()
    _stub_transport(gw, seen)

    init = gw.init_payment(
        order_id=42,
        amount=Decimal("2500.00"),
        currency="KGS",
        description="ONER — Python Basics",
    )

    assert init == PaymentInit("901", "https://pay.kg/901")
    assert seen["pg_order_id"] == "42"
    assert seen["pg_amount"] == "2500.00"
    assert seen["pg_currency"] == "KGS"
    # Capture immediately rather than leaving the card authorized.
    assert seen["pg_auto_clearing"] == "1"
    # Unset on purpose — the hosted page then offers every enabled method.
    assert "pg_payment_system" not in seen
    assert verify_sig("init_payment.php", seen, "secret")


def test_init_payment_truncates_long_descriptions_before_signing():
    seen = {}
    gw = _gateway()
    _stub_transport(gw, seen)

    gw.init_payment(
        order_id=1,
        amount=Decimal("10.00"),
        currency="KGS",
        description="x" * 400,
    )

    assert len(seen["pg_description"]) == MAX_DESCRIPTION
    assert verify_sig("init_payment.php", seen, "secret")


def test_init_payment_fails_before_calling_out_when_creds_are_missing():
    gw = _gateway(merchant_id="", secret_key="")
    seen = {}
    _stub_transport(gw, seen)

    with pytest.raises(FreedomPayError, match="not configured"):
        gw.init_payment(
            order_id=1, amount=Decimal("10.00"), currency="KGS", description="x"
        )

    assert seen == {}


# ---- gateway response parsing ---------------------------------------------

def testparse_init_reads_payment_id_and_redirect_url():
    init = parse_init(
        "<response><pg_status>ok</pg_status>"
        "<pg_payment_id>901</pg_payment_id>"
        "<pg_redirect_url>https://pay.kg/901</pg_redirect_url></response>"
    )

    assert init.payment_id == "901"
    assert init.redirect_url == "https://pay.kg/901"


def testparse_init_raises_on_gateway_error_status():
    body = (
        "<response><pg_status>error</pg_status>"
        "<pg_error_code>555</pg_error_code>"
        "<pg_error_description>Merchant not found</pg_error_description></response>"
    )

    with pytest.raises(FreedomPayError, match="555"):
        parse_init(body)


def testparse_init_raises_when_ok_but_no_redirect_url():
    with pytest.raises(FreedomPayError):
        parse_init("<response><pg_status>ok</pg_status></response>")


def testparse_init_raises_on_non_xml_body():
    with pytest.raises(FreedomPayError, match="unparseable"):
        parse_init("502 Bad Gateway")


# ---- checkout over HTTP ---------------------------------------------------

def test_checkout_creates_pending_purchase_and_returns_link(
    client: TestClient, session: Session, gateway
):
    user = _user(session)
    course = _course(session)

    res = client.post("/checkout", json={"course_id": course.id}, headers=_auth(user))

    assert res.status_code == 201
    body = res.json()
    assert body["redirect_url"] == "https://sandbox.freedompay.kg/pay/1"
    assert body["payment_id"] == "pg-payment-1"
    assert body["status"] == PurchaseStatus.pending.value

    purchase = session.get(Purchase, body["purchase_id"])
    assert purchase.status == PurchaseStatus.pending
    assert purchase.amount == course.price
    assert purchase.currency == course.currency
    assert purchase.gateway_txn_id == "pg-payment-1"


def test_checkout_sends_purchase_id_as_order_id(
    client: TestClient, session: Session, gateway
):
    user = _user(session)
    course = _course(session)

    res = client.post("/checkout", json={"course_id": course.id}, headers=_auth(user))

    call = gateway.calls[0]
    assert call["order_id"] == res.json()["purchase_id"]
    assert call["amount"] == course.price
    assert call["currency"] == "KGS"


def test_checkout_twice_reuses_the_same_pending_purchase(
    client: TestClient, session: Session, gateway
):
    user = _user(session)
    course = _course(session)
    headers = _auth(user)

    first = client.post("/checkout", json={"course_id": course.id}, headers=headers)
    second = client.post("/checkout", json={"course_id": course.id}, headers=headers)

    assert first.json()["purchase_id"] == second.json()["purchase_id"]
    rows = session.exec(select(Purchase).where(Purchase.user_id == user.id)).all()
    assert len(rows) == 1
    assert len(gateway.calls) == 2


def test_a_price_change_opens_a_new_order_and_leaves_the_old_link_payable(
    client: TestClient, session: Session, gateway
):
    user = _user(session)
    course = _course(session, price="1000.00")
    headers = _auth(user)

    first = client.post("/checkout", json={"course_id": course.id}, headers=headers).json()
    course.price = Decimal("1500.00")
    session.add(course)
    session.commit()
    second = client.post("/checkout", json={"course_id": course.id}, headers=headers).json()

    assert second["purchase_id"] != first["purchase_id"]
    assert Decimal(second["amount"]) == Decimal("1500.00")
    assert gateway.calls[1]["amount"] == Decimal("1500.00")
    # Re-pricing the old order would make its still-open link fail the amount
    # check on callback: paid, and no course.
    old = session.get(Purchase, first["purchase_id"])
    session.refresh(old)
    assert (old.status, old.amount) == (PurchaseStatus.pending, Decimal("1000.00"))


def test_simultaneous_checkouts_share_one_order(
    client: TestClient, session: Session, gateway, monkeypatch
):
    user = _user(session)
    course = _course(session)
    headers = _auth(user)
    first = client.post("/checkout", json={"course_id": course.id}, headers=headers).json()

    real = checkout_service.pending_purchase
    lookups = []

    def not_yet_visible(*args):
        # The second click looks before the first click's order commits.
        lookups.append(args)
        return None if len(lookups) == 1 else real(*args)

    monkeypatch.setattr(checkout_service, "pending_purchase", not_yet_visible)
    second = client.post("/checkout", json={"course_id": course.id}, headers=headers)

    assert second.status_code == 201
    assert second.json()["purchase_id"] == first["purchase_id"]
    assert len(session.exec(select(Purchase).where(Purchase.user_id == user.id)).all()) == 1


def test_a_buyer_reads_the_status_of_their_own_order(
    client: TestClient, session: Session, gateway
):
    user = _user(session)
    course = _course(session)
    order = client.post("/checkout", json={"course_id": course.id}, headers=_auth(user)).json()

    res = client.get(f"/me/purchases/{order['purchase_id']}", headers=_auth(user))

    assert res.status_code == 200
    body = res.json()
    assert (body["status"], body["course_id"], body["amount"]) == ("pending", course.id, "2500.00")
    assert body["created_at"].endswith("Z")


def test_someone_elses_order_is_404(client: TestClient, session: Session, gateway):
    buyer = _user(session)
    course = _course(session)
    order = client.post("/checkout", json={"course_id": course.id}, headers=_auth(buyer)).json()
    other = _user(session, "other@oner.kg")

    res = client.get(f"/me/purchases/{order['purchase_id']}", headers=_auth(other))

    assert res.status_code == 404


def test_order_status_requires_authentication(client: TestClient):
    assert client.get("/me/purchases/1").status_code == 401


def test_checkout_rejects_a_course_the_user_already_owns(
    client: TestClient, session: Session
):
    user = _user(session)
    course = _course(session)
    session.add(Entitlement(user_id=user.id, course_id=course.id))
    session.commit()

    res = client.post("/checkout", json={"course_id": course.id}, headers=_auth(user))

    assert res.status_code == 409


def test_checkout_hides_draft_courses_behind_404(client: TestClient, session: Session):
    user = _user(session)
    course = _course(session, status=CourseStatus.draft)

    res = client.post("/checkout", json={"course_id": course.id}, headers=_auth(user))

    assert res.status_code == 404


def test_checkout_rejects_a_course_with_no_price(client: TestClient, session: Session):
    user = _user(session)
    course = _course(session, price="0.00")

    res = client.post("/checkout", json={"course_id": course.id}, headers=_auth(user))

    assert res.status_code == 400


def test_checkout_requires_authentication(client: TestClient, session: Session):
    course = _course(session)

    res = client.post("/checkout", json={"course_id": course.id})

    assert res.status_code == 401


def test_checkout_returns_502_when_the_gateway_fails(
    client: TestClient, session: Session, gateway
):
    user = _user(session)
    course = _course(session)
    gateway.error = FreedomPayError("init_payment rejected: 555 merchant not found")

    res = client.post("/checkout", json={"course_id": course.id}, headers=_auth(user))

    assert res.status_code == 502
    # The pending purchase survives so a retry reuses it instead of orphaning rows.
    rows = session.exec(select(Purchase).where(Purchase.user_id == user.id)).all()
    assert len(rows) == 1
    assert rows[0].gateway_txn_id is None


def test_checkout_grants_no_access(client: TestClient, session: Session):
    """The whole point of Day 6: a payment link is not a purchase."""
    user = _user(session)
    course = _course(session)

    client.post("/checkout", json={"course_id": course.id}, headers=_auth(user))

    owned = session.exec(
        select(Entitlement).where(Entitlement.user_id == user.id)
    ).all()
    assert owned == []
    assert client.get("/me/courses", headers=_auth(user)).json() == []
