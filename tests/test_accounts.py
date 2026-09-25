"""Admin support: find an account, see what it owns and paid for, and change
what an admin may change on it. Disabling is the change that has to reach every
door at once."""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.security import (
    create_access_token,
    create_drm_token,
    create_refresh_token,
    hash_password,
)
from app.models import (
    Course,
    CourseStatus,
    Currency,
    Lesson,
    Module,
    Purchase,
    PurchaseStatus,
    User,
    UserRole,
)
from app.services.entitlements import grant
from app.services.storage import new_storage_key

PASSWORD = "supersecret123"


def _user(
    session: Session,
    email: str,
    role: UserRole = UserRole.student,
    *,
    created_at: datetime | None = None,
) -> User:
    user = User(email=email, password_hash=hash_password(PASSWORD), role=role)
    if created_at is not None:
        user.created_at = created_at
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def _course(
    session: Session,
    slug: str = "python-basics",
    *,
    video_id: str | None = None,
    status: CourseStatus = CourseStatus.published,
) -> Course:
    course = Course(
        title=slug.title(),
        slug=slug,
        price=Decimal("2500.00"),
        currency=Currency.KGS,
        status=status,
    )
    module = Module(title="M1", order=0)
    module.lessons.append(Lesson(title="L1", order=0, kinescope_video_id=video_id))
    course.modules.append(module)
    session.add(course)
    session.commit()
    session.refresh(course)
    return course


def _purchase(
    session: Session,
    user: User,
    course: Course,
    status: PurchaseStatus,
    *,
    minutes_ago: int,
    txn: str | None = None,
) -> Purchase:
    purchase = Purchase(
        user_id=user.id,
        course_id=course.id,
        amount=course.price,
        currency=course.currency,
        status=status,
        gateway_txn_id=txn,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
    )
    session.add(purchase)
    session.commit()
    session.refresh(purchase)
    return purchase


@pytest.fixture
def admin(session: Session) -> User:
    return _user(session, "admin@oner.kg", UserRole.admin)


@pytest.fixture
def headers(admin: User) -> dict:
    return _auth(admin)


# ---- finding accounts ------------------------------------------------------

def test_find_users_by_part_of_an_email_ignoring_case(
    client: TestClient, session: Session, headers: dict
):
    _user(session, "Aigul.T@mail.ru")
    _user(session, "bakyt@gmail.com")

    body = client.get("/admin/users", params={"email": "aigul"}, headers=headers).json()

    assert [u["email"] for u in body["items"]] == ["Aigul.T@mail.ru"]
    assert body["total"] == 1


def test_email_search_treats_wildcards_as_plain_characters(
    client: TestClient, session: Session, headers: dict
):
    _user(session, "a_b@mail.ru")
    _user(session, "axb@mail.ru")

    body = client.get("/admin/users", params={"email": "a_b"}, headers=headers).json()

    assert [u["email"] for u in body["items"]] == ["a_b@mail.ru"]


def test_user_search_pages_newest_first(client: TestClient, session: Session, headers: dict):
    now = datetime.now(timezone.utc)
    for i in range(3):
        _user(session, f"s{i}@oner.kg", created_at=now + timedelta(minutes=i))

    first = client.get(
        "/admin/users", params={"email": "@oner.kg", "limit": 2}, headers=headers
    ).json()
    second = client.get(
        "/admin/users", params={"email": "@oner.kg", "limit": 2, "offset": 2}, headers=headers
    ).json()

    assert [u["email"] for u in first["items"]] == ["s2@oner.kg", "s1@oner.kg"]
    assert [u["email"] for u in second["items"]] == ["s0@oner.kg", "admin@oner.kg"]
    assert first["total"] == second["total"] == 4


def test_page_size_is_capped_at_100(client: TestClient, headers: dict):
    assert client.get("/admin/users", params={"limit": 101}, headers=headers).status_code == 422


def test_an_account_shows_what_it_owns_and_every_payment_attempt(
    client: TestClient, session: Session, headers: dict
):
    buyer = _user(session, "buyer@oner.kg")
    bought = _course(session, "python-basics")
    gifted = _course(session, "react-basics")
    abandoned = _course(session, "sql-basics")
    paid = _purchase(session, buyer, bought, PurchaseStatus.paid, minutes_ago=30, txn="pg-1")
    grant(session, buyer.id, bought.id, source_purchase_id=paid.id)
    grant(session, buyer.id, gifted.id)
    _purchase(session, buyer, abandoned, PurchaseStatus.pending, minutes_ago=5)

    body = client.get(f"/admin/users/{buyer.id}", headers=headers).json()

    assert body["email"] == "buyer@oner.kg"
    assert {(o["course_title"], o["source_purchase_id"]) for o in body["owned_courses"]} == {
        ("Python-Basics", paid.id),
        ("React-Basics", None),
    }
    assert [(p["course_title"], p["status"]) for p in body["purchases"]] == [
        ("Sql-Basics", "pending"),
        ("Python-Basics", "paid"),
    ]


def test_an_unknown_account_is_404(client: TestClient, headers: dict):
    assert client.get("/admin/users/9999", headers=headers).status_code == 404
    assert client.patch("/admin/users/9999", json={"role": "admin"}, headers=headers).status_code == 404


def test_students_cannot_look_up_accounts_or_payments(client: TestClient, session: Session):
    student = _user(session, "student@oner.kg")

    assert client.get("/admin/users", headers=_auth(student)).status_code == 403
    assert client.get("/admin/purchases", headers=_auth(student)).status_code == 403


def test_account_lookup_requires_authentication(client: TestClient):
    assert client.get("/admin/users").status_code == 401


# ---- changing an account -----------------------------------------------------

def test_promoting_a_user_takes_effect_on_their_next_request(
    client: TestClient, session: Session, headers: dict
):
    helper = _user(session, "helper@oner.kg")
    token = _auth(helper)
    assert client.get("/admin/users", headers=token).status_code == 403

    res = client.patch(f"/admin/users/{helper.id}", json={"role": "admin"}, headers=headers)

    assert res.json()["role"] == "admin"
    assert client.get("/admin/users", headers=token).status_code == 200


def test_the_last_active_admin_cannot_be_demoted(client: TestClient, headers: dict, admin: User):
    res = client.patch(f"/admin/users/{admin.id}", json={"role": "student"}, headers=headers)

    assert res.status_code == 409


def test_the_last_active_admin_cannot_be_disabled(client: TestClient, headers: dict, admin: User):
    res = client.patch(f"/admin/users/{admin.id}", json={"is_active": False}, headers=headers)

    assert res.status_code == 409


def test_an_admin_can_be_demoted_while_another_remains(
    client: TestClient, session: Session, headers: dict
):
    second = _user(session, "second@oner.kg", UserRole.admin)

    res = client.patch(f"/admin/users/{second.id}", json={"role": "student"}, headers=headers)

    assert res.status_code == 200


def test_a_disabled_admin_does_not_count_as_the_one_that_remains(
    client: TestClient, session: Session, headers: dict, admin: User
):
    second = _user(session, "second@oner.kg", UserRole.admin)
    client.patch(f"/admin/users/{second.id}", json={"is_active": False}, headers=headers)

    res = client.patch(f"/admin/users/{admin.id}", json={"role": "student"}, headers=headers)

    assert res.status_code == 409


def test_setting_a_new_password_replaces_the_old_one(
    client: TestClient, session: Session, headers: dict
):
    user = _user(session, "forgot@oner.kg")

    client.patch(f"/admin/users/{user.id}", json={"password": "brand-new-pass-1"}, headers=headers)
    old = client.post("/auth/login", data={"username": "forgot@oner.kg", "password": PASSWORD})
    new = client.post(
        "/auth/login", data={"username": "forgot@oner.kg", "password": "brand-new-pass-1"}
    )

    assert old.status_code == 401
    assert new.status_code == 200


def test_a_short_password_is_rejected(client: TestClient, session: Session, headers: dict):
    user = _user(session, "short@oner.kg")

    res = client.patch(f"/admin/users/{user.id}", json={"password": "short"}, headers=headers)

    assert res.status_code == 422


def test_an_admin_cannot_change_an_email(client: TestClient, session: Session, headers: dict):
    user = _user(session, "owner@oner.kg")

    res = client.patch(
        f"/admin/users/{user.id}", json={"email": "someone-else@oner.kg"}, headers=headers
    )

    assert res.status_code == 422


@pytest.mark.parametrize("field", ["role", "is_active", "password"])
def test_nulling_an_account_field_is_a_422(
    client: TestClient, session: Session, headers: dict, field: str
):
    user = _user(session, "nulls@oner.kg")

    res = client.patch(f"/admin/users/{user.id}", json={field: None}, headers=headers)

    assert res.status_code == 422


def test_account_changes_are_logged_without_the_password(
    client: TestClient, session: Session, headers: dict, caplog
):
    user = _user(session, "audited@oner.kg")

    with caplog.at_level(logging.INFO, logger="app.api.admin_accounts"):
        client.patch(
            f"/admin/users/{user.id}",
            json={"password": "brand-new-pass-1", "role": "admin"},
            headers=headers,
        )

    line = next(r.getMessage() for r in caplog.records if r.name == "app.api.admin_accounts")
    assert "password" in line and "role" in line
    assert "brand-new-pass-1" not in line


# ---- disabled accounts ---------------------------------------------------------

@pytest.fixture
def disabled(client: TestClient, session: Session, headers: dict) -> User:
    user = _user(session, "banned@oner.kg")
    client.patch(f"/admin/users/{user.id}", json={"is_active": False}, headers=headers)
    return user


def test_a_disabled_account_cannot_log_in(client: TestClient, disabled: User):
    res = client.post("/auth/login", data={"username": "banned@oner.kg", "password": PASSWORD})

    assert res.status_code == 403


def test_a_wrong_password_on_a_disabled_account_still_says_wrong_password(
    client: TestClient, disabled: User
):
    # Otherwise "Account disabled" would confirm to anyone guessing that the
    # email has an account.
    res = client.post("/auth/login", data={"username": "banned@oner.kg", "password": "nope12345"})

    assert res.status_code == 401


def test_a_disabled_account_is_locked_out_with_the_tokens_it_already_has(
    client: TestClient, disabled: User
):
    assert client.get("/auth/me", headers=_auth(disabled)).status_code == 403
    assert client.post(
        "/auth/refresh", json={"refresh_token": create_refresh_token(disabled.id)}
    ).status_code == 403


def test_a_disabled_owner_cannot_play_or_download(
    client: TestClient, session: Session, headers: dict
):
    owner = _user(session, "owner2@oner.kg")
    course = _course(session, video_id="kine-1")
    grant(session, owner.id, course.id)
    lesson_id = course.modules[0].lessons[0].id
    material_id = client.post(
        "/admin/materials",
        json={"title": "Workbook", "storage_key": new_storage_key("wb.pdf"), "course_id": course.id},
        headers=headers,
    ).json()["id"]
    drm_token = create_drm_token(owner.id, "kine-1")  # minted before the ban

    client.patch(f"/admin/users/{owner.id}", json={"is_active": False}, headers=headers)

    assert client.post(f"/video/{lesson_id}/token", headers=_auth(owner)).status_code == 403
    assert client.get(f"/materials/{material_id}/download", headers=_auth(owner)).status_code == 403
    # Kinescope asking to release the key for a player that already has a token.
    assert client.post("/drm/auth", json={"id": "kine-1", "token": drm_token}).status_code == 403


def test_a_disabled_admin_browses_the_catalog_as_anonymous(
    client: TestClient, session: Session, headers: dict
):
    former = _user(session, "former-admin@oner.kg", UserRole.admin)
    _course(session, "secret-draft", status=CourseStatus.draft)
    client.patch(f"/admin/users/{former.id}", json={"is_active": False}, headers=headers)

    assert [c["slug"] for c in client.get("/courses", headers=headers).json()] == ["secret-draft"]
    assert client.get("/courses", headers=_auth(former)).json() == []


def test_re_enabling_an_account_restores_access(
    client: TestClient, headers: dict, disabled: User
):
    client.patch(f"/admin/users/{disabled.id}", json={"is_active": True}, headers=headers)

    res = client.post("/auth/login", data={"username": "banned@oner.kg", "password": PASSWORD})

    assert res.status_code == 200


# ---- transaction history -------------------------------------------------------

@pytest.fixture
def history(session: Session) -> dict:
    aigul = _user(session, "aigul@mail.ru")
    bakyt = _user(session, "bakyt@gmail.com")
    course = _course(session)
    _purchase(session, aigul, course, PurchaseStatus.paid, minutes_ago=60, txn="pg-1")
    _purchase(session, bakyt, course, PurchaseStatus.failed, minutes_ago=30)
    _purchase(session, aigul, course, PurchaseStatus.pending, minutes_ago=1)
    return {"aigul": aigul, "course": course}


def test_history_is_newest_first_with_buyer_and_course(
    client: TestClient, headers: dict, history: dict
):
    body = client.get("/admin/purchases", headers=headers).json()

    assert body["total"] == 3
    assert [(p["user_email"], p["status"]) for p in body["items"]] == [
        ("aigul@mail.ru", "pending"),
        ("bakyt@gmail.com", "failed"),
        ("aigul@mail.ru", "paid"),
    ]
    paid = body["items"][2]
    assert (paid["course_title"], paid["gateway_txn_id"], paid["amount"]) == (
        "Python-Basics",
        "pg-1",
        "2500.00",
    )


@pytest.mark.parametrize(
    "params, total",
    [
        ({"email": "AIGUL"}, 2),
        ({"status": "failed"}, 1),
        ({"status": "pending", "email": "aigul"}, 1),
        ({"status": "paid", "email": "bakyt"}, 0),
    ],
)
def test_history_filters(
    client: TestClient, headers: dict, history: dict, params: dict, total: int
):
    assert client.get("/admin/purchases", params=params, headers=headers).json()["total"] == total


def test_history_filters_by_course(
    client: TestClient, session: Session, headers: dict, history: dict
):
    other = _course(session, "react-basics")
    _purchase(session, history["aigul"], other, PurchaseStatus.paid, minutes_ago=10, txn="pg-2")

    body = client.get("/admin/purchases", params={"course_id": other.id}, headers=headers).json()

    assert [p["course_title"] for p in body["items"]] == ["React-Basics"]


def test_an_unknown_status_filter_is_a_422(client: TestClient, headers: dict):
    assert client.get("/admin/purchases", params={"status": "chargeback"}, headers=headers).status_code == 422
