"""Shared rate limiter. One instance so routes and the app wire to the same store."""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings

# How many login attempts per IP per minute before a 429.
LOGIN_RATE_LIMIT = "5/minute"

# Registration hashes a password with argon2, which is expensive on purpose, so
# an open register route is a cheap way to burn our CPU. Looser than login
# because mobile carriers put many real users behind one IP.
REGISTER_RATE_LIMIT = "10/minute"

# Checkout hits FreedomPay on every call — throttle so one account can't hammer
# the merchant account.
CHECKOUT_RATE_LIMIT = "10/minute"


def client_ip(request: Request, header: str = "") -> str:
    """The caller's IP, which is what every limit is counted against.

    Behind a proxy the socket address is the proxy's, and then all users share
    one bucket. A platform that overwrites a header with the real IP can be
    trusted for it (Settings.trusted_ip_header); uvicorn behind Railway or DO
    gets the same from FORWARDED_ALLOW_IPS instead.
    """
    if header:
        first = request.headers.get(header, "").split(",")[0].strip()
        if first:
            return first
    return get_remote_address(request)


def _limit_key(request: Request) -> str:
    return client_ip(request, get_settings().trusted_ip_header)


# In-memory storage counts per process. That's exact for one API process; with
# several (replicas, or serverless instances) each keeps its own count, so a
# limit is looser than it reads. Swap to Redis storage_uri when that matters.
limiter = Limiter(key_func=_limit_key)


def rate_limit_exceeded(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """A 429 in the same {"detail": ...} shape as every other error.

    slowapi's built-in handler answers {"error": ...}, which would leave the
    frontend special-casing this one status.
    """
    return JSONResponse(
        {"detail": f"Rate limit exceeded: {exc.detail}"},
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    )
