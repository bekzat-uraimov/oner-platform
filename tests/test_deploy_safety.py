"""What has to hold before the API sits on a public URL: no known JWT secret,
rate limits keyed on the real caller, and timestamps a browser can't misread."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError
from starlette.requests import Request

from app.core.config import DEFAULT_JWT_SECRET, Settings
from app.core.limiter import client_ip
from app.models import UserRole
from app.schemas import UserRead


# ---- JWT secret ---------------------------------------------------------------

def test_a_deployed_environment_refuses_the_default_jwt_secret():
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(_env_file=None, environment="production", jwt_secret=DEFAULT_JWT_SECRET)


def test_a_short_jwt_secret_is_refused_outside_development():
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(_env_file=None, environment="test", jwt_secret="ci-test-secret")


def test_a_long_random_secret_starts():
    assert Settings(_env_file=None, environment="production", jwt_secret="a" * 64)


def test_local_development_may_keep_the_default():
    settings = Settings(_env_file=None, environment="development", jwt_secret=DEFAULT_JWT_SECRET)

    assert settings.jwt_secret == DEFAULT_JWT_SECRET


def test_a_blank_jwt_secret_in_the_environment_is_still_refused(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("JWT_SECRET", "")

    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(_env_file=None)


# ---- blank environment variables ------------------------------------------------

def test_blank_variables_fall_back_to_their_defaults(monkeypatch):
    # Vercel keeps a variable added with no value as "", and "" is no int.
    for name in (
        "ACCESS_TOKEN_TTL_MIN",
        "REFRESH_TOKEN_TTL_DAYS",
        "FREEDOMPAY_TESTING_MODE",
        "FREEDOMPAY_TIMEOUT_S",
        "FREEDOMPAY_INIT_URL",
        "DRM_TOKEN_TTL_MIN",
        "MATERIAL_URL_TTL_S",
        "CORS_ORIGINS",
    ):
        monkeypatch.setenv(name, "")

    settings = Settings(_env_file=None)

    assert settings.access_token_ttl_min == 15
    assert settings.freedompay_testing_mode == 1
    assert settings.freedompay_timeout_s == 10.0
    assert settings.freedompay_init_url == "https://api.freedompay.kg/init_payment.php"
    assert settings.material_url_ttl_s == 60
    assert settings.cors_origins == []


# ---- rate limit key ------------------------------------------------------------

def _request(headers: dict[str, str]) -> Request:
    return Request(
        {
            "type": "http",
            "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
            "client": ("10.0.0.1", 50000),
        }
    )


def test_without_a_trusted_header_the_key_is_the_socket_address():
    # A client-supplied header is ignored unless configured as trusted.
    assert client_ip(_request({"x-vercel-forwarded-for": "1.2.3.4"})) == "10.0.0.1"


def test_a_trusted_header_supplies_the_real_client_ip():
    request = _request({"x-vercel-forwarded-for": "1.2.3.4, 10.0.0.9"})

    assert client_ip(request, "x-vercel-forwarded-for") == "1.2.3.4"


def test_a_missing_trusted_header_falls_back_to_the_socket_address():
    assert client_ip(_request({}), "x-vercel-forwarded-for") == "10.0.0.1"


# ---- timestamps ----------------------------------------------------------------

def _user_read(created_at: datetime) -> str:
    return UserRead(id=1, email="a@oner.kg", role=UserRole.student, created_at=created_at).model_dump_json()


def test_a_timestamp_in_another_zone_leaves_as_utc():
    local = datetime(2026, 9, 14, 9, 0, tzinfo=ZoneInfo("America/Los_Angeles"))

    assert '"created_at":"2026-09-14T16:00:00Z"' in _user_read(local)


def test_a_naive_timestamp_is_read_as_utc():
    assert '"created_at":"2026-09-14T16:00:00Z"' in _user_read(datetime(2026, 9, 14, 16, 0))
