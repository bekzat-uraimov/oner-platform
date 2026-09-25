"""Rate-limited routes: login (brute force), register (argon2 CPU cost) and
checkout (gateway abuse)."""

from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import Settings
from app.core.db import get_session
from app.core.limiter import limiter
from app.core.security import create_access_token, hash_password
from app.main import create_app
from app.models import Course, CourseStatus, Currency, User
from app.services.freedompay import get_gateway


@pytest.fixture
def rate_limited_client(engine, gateway) -> Generator[TestClient, None, None]:
    def override_get_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_gateway] = lambda: gateway

    limiter.enabled = True
    limiter.reset()
    yield TestClient(app)
    app.dependency_overrides.clear()
    limiter.reset()
    limiter.enabled = False


def test_login_throttles_after_limit(rate_limited_client: TestClient) -> None:
    # LOGIN_RATE_LIMIT is 5/minute. The 6th attempt from the same IP is a 429,
    # regardless of whether credentials are valid.
    statuses = [
        rate_limited_client.post(
            "/auth/login", data={"username": "x@x.com", "password": "nope12345"}
        ).status_code
        for _ in range(6)
    ]
    assert statuses[:5] == [401, 401, 401, 401, 401]
    assert statuses[5] == 429


def test_checkout_throttles_after_limit(
    rate_limited_client: TestClient, session: Session
) -> None:
    # CHECKOUT_RATE_LIMIT is 10/minute, and every call under it reaches
    # FreedomPay. Auth resolves before the limiter, so this only throttles
    # logged-in users — which is exactly who can reach the gateway.
    user = User(email="spammer@oner.kg", password_hash=hash_password("supersecret123"))
    course = Course(
        title="Python Basics",
        slug="python-basics",
        price=Decimal("2500.00"),
        currency=Currency.KGS,
        status=CourseStatus.published,
    )
    session.add(user)
    session.add(course)
    session.commit()
    session.refresh(user)
    session.refresh(course)
    headers = {"Authorization": f"Bearer {create_access_token(user.id)}"}

    statuses = [
        rate_limited_client.post(
            "/checkout", json={"course_id": course.id}, headers=headers
        ).status_code
        for _ in range(11)
    ]
    assert statuses[:10] == [201] * 10
    assert statuses[10] == 429


def test_register_throttles_after_limit(rate_limited_client: TestClient) -> None:
    # REGISTER_RATE_LIMIT is 10/minute. Every call hashes a password with argon2,
    # so an open register route is a cheap way to burn CPU.
    statuses = [
        rate_limited_client.post(
            "/auth/register",
            json={"email": f"user{i}@oner.kg", "password": "supersecret123"},
        ).status_code
        for i in range(11)
    ]
    assert statuses[:10] == [201] * 10
    assert statuses[10] == 429


def test_a_429_has_the_same_error_shape_as_everything_else(
    rate_limited_client: TestClient,
) -> None:
    for _ in range(6):
        res = rate_limited_client.post(
            "/auth/login", data={"username": "x@x.com", "password": "nope12345"}
        )

    assert res.status_code == 429
    assert set(res.json()) == {"detail"}


def test_each_ip_from_the_trusted_header_gets_its_own_bucket(
    rate_limited_client: TestClient, monkeypatch
) -> None:
    # Behind Vercel every request arrives from the platform; without the header
    # all users would share one login limit.
    monkeypatch.setattr(
        "app.core.limiter.get_settings",
        lambda: Settings(_env_file=None, trusted_ip_header="x-vercel-forwarded-for"),
    )

    def attempts(ip: str) -> list[int]:
        return [
            rate_limited_client.post(
                "/auth/login",
                data={"username": "x@x.com", "password": "nope12345"},
                headers={"x-vercel-forwarded-for": ip},
            ).status_code
            for _ in range(6)
        ]

    assert attempts("1.1.1.1")[5] == 429
    assert attempts("2.2.2.2")[0] == 401
