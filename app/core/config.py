"""Application settings, loaded from environment / .env via pydantic-settings.

Secrets never live in git. Real values go in `.env` (gitignored); `.env.example`
documents the shape of every variable.
"""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "change-me-in-env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # A dashboard variable saved with no value arrives as "". Treat it as
        # unset, so an empty ACCESS_TOKEN_TTL_MIN falls back to its default
        # instead of failing int parsing and taking the whole app down.
        env_ignore_empty=True,
    )

    # App
    app_name: str = "ONER API"
    environment: str = "development"
    debug: bool = False
    # Browser origins allowed to call the API: the frontend and the admin page.
    # Empty means no cross-origin access at all.
    cors_origins: list[str] = []
    # A header carrying the real client IP, from a platform that overwrites
    # whatever the client sent (Vercel: x-vercel-forwarded-for). Empty means the
    # socket address. Never name a header clients can set: they'd choose their
    # own rate limit bucket.
    trusted_ip_header: str = ""

    # Database — async-friendly Postgres DSN. Default points at the docker-compose service.
    database_url: str = "postgresql+psycopg://oner:oner@localhost:5432/oner"

    # Auth (used from Day 3 onward)
    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_ttl_min: int = 15
    refresh_token_ttl_days: int = 30

    # Payments — FreedomPay. Sandbox creds until the ИП merchant account exists;
    # empty defaults keep the app importable without them.
    freedompay_merchant_id: str = ""
    freedompay_secret_key: str = ""
    freedompay_init_url: str = "https://api.freedompay.kg/init_payment.php"
    freedompay_result_url: str = "http://localhost:8000/webhooks/freedompay/result"
    # Where FreedomPay sends the buyer's browser afterwards: frontend pages.
    freedompay_success_url: str = "http://localhost:3000/checkout/success"
    freedompay_failure_url: str = "http://localhost:3000/checkout/failure"
    freedompay_testing_mode: int = 1
    freedompay_timeout_s: float = 10.0

    # Video — Kinescope. We mint the drmauthtoken ourselves; Kinescope calls
    # /drm/auth on playback to ask whether to release the key.
    kinescope_project_id: str = ""
    kinescope_api_key: str = ""
    # Optional Basic Auth on the callback. Kinescope offers no request
    # signature, so this is the only transport-level check available.
    kinescope_drm_auth_user: str = ""
    kinescope_drm_auth_password: str = ""
    drm_token_ttl_min: int = 10
    # Admin uploads land in this folder when set, otherwise the project root.
    kinescope_folder_id: str = ""
    # Basic Auth Kinescope sends on its status webhook, set when registering it.
    # Kinescope signs nothing, so the webhook stays closed until these are set.
    kinescope_webhook_user: str = ""
    kinescope_webhook_password: str = ""
    kinescope_timeout_s: float = 15.0

    # Materials — Cloudflare R2 (S3-compatible). Links are deliberately short:
    # a signed URL can be forwarded, and there is no DRM for a PDF.
    r2_account_id: str = ""
    r2_bucket: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    material_url_ttl_s: int = 60
    # Uploads get a longer window than downloads: the whole file has to finish
    # inside it, and only an admin ever holds one.
    material_upload_ttl_s: int = 900
    # How old an unreferenced file must be before the sweep deletes it. Covers an
    # upload whose row hasn't been recorded yet.
    material_orphan_grace_h: int = 24

    @model_validator(mode="after")
    def refuse_default_jwt_secret(self):
        # Whoever knows the secret can sign an admin token, and the default is
        # written right here. Only local development may run with it.
        if self.environment != "development" and (
            self.jwt_secret == DEFAULT_JWT_SECRET or len(self.jwt_secret) < 32
        ):
            raise ValueError(
                "JWT_SECRET must be a random value of at least 32 characters "
                "when ENVIRONMENT is not development"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so settings are parsed once per process."""
    return Settings()
