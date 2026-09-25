"""Password hashing (argon2) and JWT issuing/decoding.

All token logic lives here so the rules — what's signed, the expiry, the access
vs refresh distinction — sit in one auditable place.
"""

from datetime import timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.models.base import utcnow

settings = get_settings()

# argon2 — modern, memory-hard. deprecated="auto" lets us add schemes later and
# transparently re-hash on login.
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

ACCESS = "access"
REFRESH = "refresh"
DRM = "drm"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _create_token(subject: int, token_type: str, ttl: timedelta, **claims) -> str:
    now = utcnow()
    payload = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + ttl,
        **claims,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int) -> str:
    return _create_token(
        user_id, ACCESS, timedelta(minutes=settings.access_token_ttl_min)
    )


def create_refresh_token(user_id: int) -> str:
    return _create_token(
        user_id, REFRESH, timedelta(days=settings.refresh_token_ttl_days)
    )


def create_drm_token(user_id: int, video_id: str) -> str:
    """Token the player hands to Kinescope as `drmauthtoken`.

    Bound to one video so it can't be reused to unlock a different course, and
    short-lived because Kinescope's auth callback is the only thing that checks
    it and we can't revoke a token already in a player.
    """
    return _create_token(
        user_id,
        DRM,
        timedelta(minutes=settings.drm_token_ttl_min),
        vid=video_id,
    )


def decode_token(token: str) -> dict:
    """Decode + verify a JWT. Raises jose.JWTError on bad signature or expiry."""
    return jwt.decode(
        token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
    )


__all__ = [
    "ACCESS",
    "DRM",
    "REFRESH",
    "JWTError",
    "create_access_token",
    "create_drm_token",
    "create_refresh_token",
    "decode_token",
    "hash_password",
    "verify_password",
] 