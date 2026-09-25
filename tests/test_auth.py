"""Day 3: nobody touches protected routes without a valid access token."""

from datetime import timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jose import jwt

from app.api.deps import require_admin
from app.services import auth as auth_service
from app.services.auth import EmailAlreadyRegistered, register_user
from app.core.config import get_settings
from app.models import User, UserRole
from app.models.base import utcnow

EMAIL = "user@example.com"
PASSWORD = "supersecret123"


def _register(client: TestClient, email: str = EMAIL, password: str = PASSWORD):
    return client.post("/auth/register", json={"email": email, "password": password})


def _login(client: TestClient, email: str = EMAIL, password: str = PASSWORD):
    return client.post(
        "/auth/login", data={"username": email, "password": password}
    )


# ---- register -------------------------------------------------------------

def test_register_returns_user_without_password(client: TestClient) -> None:
    resp = _register(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == EMAIL
    assert body["role"] == "student"
    assert "password" not in body and "password_hash" not in body


def test_register_duplicate_email_conflicts(client: TestClient) -> None:
    _register(client)
    resp = _register(client)
    assert resp.status_code == 409


def test_register_stores_the_email_lowercased(client: TestClient) -> None:
    resp = _register(client, email="Aigul@Mail.RU")

    assert resp.json()["email"] == "aigul@mail.ru"


def test_the_same_email_in_another_case_is_already_registered(client: TestClient) -> None:
    _register(client, email="aigul@mail.ru")

    assert _register(client, email="AIGUL@mail.ru").status_code == 409


def test_login_ignores_the_case_of_the_email(client: TestClient) -> None:
    # Phone keyboards capitalise the first letter.
    _register(client, email="aigul@mail.ru")

    assert _login(client, email="Aigul@mail.ru").status_code == 200


def test_a_simultaneous_signup_with_the_same_email_is_a_conflict_not_a_500(
    session, monkeypatch
) -> None:
    register_user(session, "aigul@mail.ru", PASSWORD)
    # The second request checked before the first one committed.
    monkeypatch.setattr(auth_service, "get_user_by_email", lambda *args: None)

    with pytest.raises(EmailAlreadyRegistered):
        register_user(session, "aigul@mail.ru", PASSWORD)


def test_register_rejects_short_password(client: TestClient) -> None:
    resp = _register(client, password="short")
    assert resp.status_code == 422


# ---- login ----------------------------------------------------------------

def test_login_success_returns_tokens(client: TestClient) -> None:
    _register(client)
    resp = _login(client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_login_wrong_password_401(client: TestClient) -> None:
    _register(client)
    resp = _login(client, password="wrongpassword")
    assert resp.status_code == 401


def test_login_unknown_email_401(client: TestClient) -> None:
    resp = _login(client, email="nobody@example.com")
    assert resp.status_code == 401


# ---- protected route + token rules ----------------------------------------

def test_me_requires_token(client: TestClient) -> None:
    assert client.get("/auth/me").status_code == 401


def test_me_with_access_token(client: TestClient) -> None:
    _register(client)
    access = _login(client).json()["access_token"]
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == EMAIL


def test_me_rejects_refresh_token(client: TestClient) -> None:
    _register(client)
    refresh = _login(client).json()["refresh_token"]
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {refresh}"})
    assert resp.status_code == 401


def test_me_rejects_expired_token(client: TestClient) -> None:
    settings = get_settings()
    payload = {
        "sub": "1",
        "type": "access",
        "iat": utcnow() - timedelta(hours=2),
        "exp": utcnow() - timedelta(hours=1),  # already expired
    }
    expired = jwt.encode(
        payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401


def test_me_rejects_garbage_token(client: TestClient) -> None:
    resp = client.get("/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401


# ---- refresh --------------------------------------------------------------

def test_refresh_issues_working_access_token(client: TestClient) -> None:
    _register(client)
    refresh = _login(client).json()["refresh_token"]
    resp = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    new_access = resp.json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert me.status_code == 200


def test_refresh_rejects_access_token(client: TestClient) -> None:
    _register(client)
    access = _login(client).json()["access_token"]
    resp = client.post("/auth/refresh", json={"refresh_token": access})
    assert resp.status_code == 401


# ---- role gate (unit) -----------------------------------------------------

def test_require_admin_allows_admin() -> None:
    admin = User(id=1, email="a@x.com", password_hash="x", role=UserRole.admin)
    assert require_admin(admin) is admin


def test_require_admin_blocks_student() -> None:
    student = User(id=2, email="s@x.com", password_hash="x", role=UserRole.student)
    with pytest.raises(HTTPException) as exc:
        require_admin(student)
    assert exc.value.status_code == 403


def test_timestamps_come_back_in_utc_with_an_offset(client: TestClient) -> None:
    _register(client)
    token = _login(client).json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()

    assert me["created_at"].endswith("Z")
