"""Shared pytest fixtures."""

from collections.abc import Generator

import httpx
import pytest
from botocore.stub import Stubber
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401  (registers all tables on SQLModel.metadata)
from app.core.db import get_session
from app.core.config import Settings, get_settings
from app.core.limiter import limiter
from app.main import create_app
from app.services.freedompay import PaymentInit, get_gateway
from app.services.kinescope import KinescopeClient, get_kinescope
from app.services.storage import R2Client, get_storage


def _enforce_foreign_keys(dbapi_conn, _record) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def engine() -> Generator:
    """A throwaway in-memory SQLite engine with the full schema.

    StaticPool keeps every connection pointed at the same in-memory database for
    the life of the fixture. No Postgres needed for these tests.
    """
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # SQLite ignores foreign keys unless asked, and Postgres never does. Without
    # this, a delete that breaks a reference passes here and 500s in production.
    event.listen(eng, "connect", _enforce_foreign_keys)
    SQLModel.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine) -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


# Webhook tests sign their payloads with these, so they have to match whatever
# the fake gateway reports.
TEST_SECRET = "test-secret"
TEST_RESULT_URL = "https://oner.kg/webhooks/freedompay/result"


class FakeGateway:
    """Stand-in for FreedomPay. Records calls; never touches the network.

    Carries the same credential attributes as the real client, since signature
    verification on the webhook path is pure computation and needs no stubbing.
    Set `error` to an exception to make the next init_payment raise it.
    """

    def __init__(self):
        self.calls = []
        self.error: Exception | None = None
        self.secret_key = TEST_SECRET
        self.result_url = TEST_RESULT_URL
        self.testing_mode = 1

    def init_payment(self, **kwargs) -> PaymentInit:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        n = len(self.calls)
        return PaymentInit(
            payment_id=f"pg-payment-{n}",
            redirect_url=f"https://sandbox.freedompay.kg/pay/{n}",
        )


@pytest.fixture
def gateway() -> FakeGateway:
    return FakeGateway()


class FakeKinescope:
    """Stand-in for Kinescope's API and uploader, served through
    httpx.MockTransport so the real client builds real requests.

    `videos` is what Kinescope holds; set a video's status to "done" to finish
    its processing. `requests` is everything the app sent. Set `fail` to make
    every call answer 500.
    """

    def __init__(self):
        self.videos: dict[str, dict] = {}
        self.requests: list[httpx.Request] = []
        self.fail = False
        self._next = 1

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail:
            return httpx.Response(
                500, json={"error": {"code": 500000, "message": "internal error"}}
            )

        path = request.url.path
        if request.method == "POST" and path == "/v2/init":
            video_id = f"vid-{self._next}"
            self._next += 1
            self.videos[video_id] = {"status": "pending", "duration": None}
            return httpx.Response(
                200,
                json={
                    "data": {
                        "id": video_id,
                        "endpoint": f"https://eu-ams-uploader-1.kinescope.io/v2/upload/{video_id}",
                    }
                },
            )

        video_id = path.removeprefix("/v1/videos/")
        if video_id not in self.videos:
            return httpx.Response(
                404, json={"error": {"code": 404404, "message": "video not found"}}
            )
        if request.method == "GET":
            return httpx.Response(200, json={"data": {"id": video_id, **self.videos[video_id]}})
        del self.videos[video_id]
        return httpx.Response(200, json={"data": {"success": True}})


@pytest.fixture
def kinescope_api() -> FakeKinescope:
    return FakeKinescope()


@pytest.fixture
def kinescope(kinescope_api: FakeKinescope) -> KinescopeClient:
    client = KinescopeClient(api_key="kinescope-test-key", parent_id="project-1", timeout=5)
    client.http = httpx.Client(transport=httpx.MockTransport(kinescope_api.handle))
    return client


@pytest.fixture
def storage() -> R2Client:
    """A real R2 client with throwaway credentials.

    Presigning is pure local computation, so this signs genuine URLs without a
    bucket or a network call. Set `configured = False` to simulate a deployment
    with no R2 credentials.
    """
    return R2Client(
        account_id="testacct",
        bucket="oner-test",
        access_key_id="AKIAEXAMPLE",
        secret_access_key="test-secret-key",
        url_ttl_s=60,
        upload_ttl_s=900,
    )


@pytest.fixture
def r2(storage) -> Generator[Stubber, None, None]:
    """Stands in for R2 itself.

    Presigning never leaves the process, but deletes and listings are real
    requests. This is always active under `client`, so no test can reach the
    network; a test that cares queues the exact requests it expects and asserts
    they were all made.
    """
    with Stubber(storage._s3) as stubber:
        yield stubber


@pytest.fixture
def settings() -> Settings:
    """Settings the app sees, so a test can turn a feature on mid-test.

    Kinescope Basic Auth is off by default here; the tests that care switch it
    on before making a request.
    """
    return Settings(kinescope_drm_auth_user="", kinescope_drm_auth_password="")


@pytest.fixture
def client(
    engine, gateway, settings, storage, r2, kinescope
) -> Generator[TestClient, None, None]:
    """TestClient whose `get_session` is wired to the in-memory engine.

    Rate limiting is disabled here so functional tests aren't throttled; the
    dedicated rate-limit test re-enables it.
    """

    def override_get_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app = create_app(settings)
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_gateway] = lambda: gateway
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_kinescope] = lambda: kinescope

    limiter.enabled = False
    limiter.reset()
    yield TestClient(app)
    app.dependency_overrides.clear()
    limiter.enabled = True
