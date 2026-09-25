"""FastAPI application factory.

Keeping creation in a factory keeps tests honest: each test can build a fresh
app instance instead of importing a module-level singleton.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from app.api import (
    admin,
    admin_accounts,
    admin_video,
    auth,
    checkout,
    courses,
    drm,
    health,
    materials,
    me,
    video,
    webhooks,
)
from app.core.config import Settings, get_settings
from app.core.limiter import limiter, rate_limit_exceeded
from app.core.logs import RequestLogMiddleware, setup_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = get_settings()
    setup_logging()
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
    )

    # Rate limiting (login, register, checkout; see app.core.limiter).
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(courses.router)
    app.include_router(me.router)
    app.include_router(checkout.router)
    app.include_router(webhooks.router)
    app.include_router(video.router)
    app.include_router(drm.router)
    app.include_router(materials.router)
    app.include_router(admin.router)
    app.include_router(admin_accounts.router)
    app.include_router(admin_video.router)

    # The last middleware added runs first. CORS sits outside the request log so
    # even the JSON 500 written there carries CORS headers; a browser can't read
    # an error response it isn't allowed to see.
    app.add_middleware(RequestLogMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    return app


app = create_app()
