"""Day 11 — hardening.

Nothing here is a feature. Each test pins down a way the API used to fail
badly (a 500, a false error, a header it shouldn't send) or a guard a deployed
frontend depends on.
"""

import json
import logging
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import Settings
from app.core.logs import JsonFormatter
from app.core.security import create_access_token, hash_password
from app.main import create_app
from app.models import Course, Entitlement, Lesson, Material, PriceAudit, User, UserRole
from app.services.storage import download_filename, new_storage_key


def _user(session: Session, email: str, role: UserRole = UserRole.student) -> User:
    user = User(email=email, password_hash=hash_password("supersecret123"), role=role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def _boom():
    raise RuntimeError("kaboom")


@pytest.fixture
def headers(session: Session) -> dict:
    return _auth(_user(session, "admin@oner.kg", UserRole.admin))


@pytest.fixture
def course(client: TestClient, headers: dict) -> dict:
    return client.post(
        "/admin/courses",
        json={
            "title": "Python Basics",
            "slug": "python-basics",
            "price": "2500.00",
            "status": "published",
        },
        headers=headers,
    ).json()


@pytest.fixture
def module(client: TestClient, headers: dict, course: dict) -> dict:
    return client.post(
        f"/admin/courses/{course['id']}/modules", json={"title": "Day 1"}, headers=headers
    ).json()


@pytest.fixture
def lesson(client: TestClient, headers: dict, module: dict) -> dict:
    return client.post(
        f"/admin/modules/{module['id']}/lessons", json={"title": "Variables"}, headers=headers
    ).json()


# ---- PATCH can't null a required column ------------------------------------

@pytest.mark.parametrize("field", ["title", "slug", "price", "currency", "status"])
def test_nulling_a_required_course_field_is_a_422(
    client: TestClient, headers: dict, course: dict, field: str
):
    # Used to reach the database: a 500, or a false "Slug already in use".
    res = client.patch(
        f"/admin/courses/{course['id']}", json={field: None}, headers=headers
    )

    assert res.status_code == 422


def test_nulling_an_optional_course_field_still_clears_it(
    client: TestClient, headers: dict, course: dict
):
    client.patch(
        f"/admin/courses/{course['id']}", json={"description": "Intro"}, headers=headers
    )

    res = client.patch(
        f"/admin/courses/{course['id']}", json={"description": None}, headers=headers
    )

    assert res.status_code == 200
    assert res.json()["description"] is None


@pytest.mark.parametrize(
    "kind, field",
    [("modules", "title"), ("modules", "order"), ("lessons", "title"), ("lessons", "order")],
)
def test_nulling_a_required_module_or_lesson_field_is_a_422(
    client: TestClient, headers: dict, module: dict, lesson: dict, kind: str, field: str
):
    target = module if kind == "modules" else lesson

    res = client.patch(f"/admin/{kind}/{target['id']}", json={field: None}, headers=headers)

    assert res.status_code == 422


@pytest.mark.parametrize("field", ["title", "type"])
def test_nulling_a_required_material_field_is_a_422(
    client: TestClient, headers: dict, course: dict, field: str
):
    material = client.post(
        "/admin/materials",
        json={
            "title": "Workbook",
            "storage_key": new_storage_key("wb.pdf"),
            "course_id": course["id"],
        },
        headers=headers,
    ).json()

    res = client.patch(
        f"/admin/materials/{material['id']}", json={field: None}, headers=headers
    )

    assert res.status_code == 422


# ---- video ids ---------------------------------------------------------------

@pytest.mark.parametrize("value", ["", "   "])
def test_a_blank_video_id_is_rejected(
    client: TestClient, headers: dict, module: dict, lesson: dict, value: str
):
    created = client.post(
        f"/admin/modules/{module['id']}/lessons",
        json={"title": "L2", "kinescope_video_id": value},
        headers=headers,
    )
    patched = client.patch(
        f"/admin/lessons/{lesson['id']}", json={"kinescope_video_id": value}, headers=headers
    )

    assert created.status_code == 422
    assert patched.status_code == 422


def test_video_ids_are_trimmed(client: TestClient, headers: dict, lesson: dict):
    res = client.patch(
        f"/admin/lessons/{lesson['id']}",
        json={"kinescope_video_id": "  kine-1  "},
        headers=headers,
    )

    assert res.json()["kinescope_video_id"] == "kine-1"


def test_null_still_detaches_a_video(client: TestClient, headers: dict, lesson: dict):
    client.patch(
        f"/admin/lessons/{lesson['id']}", json={"kinescope_video_id": "kine-1"}, headers=headers
    )

    res = client.patch(
        f"/admin/lessons/{lesson['id']}", json={"kinescope_video_id": None}, headers=headers
    )

    assert res.status_code == 200
    assert res.json()["kinescope_video_id"] is None


def test_lesson_detail_and_the_token_route_agree_on_a_blank_video_id(
    client: TestClient, session: Session, headers: dict, course: dict, lesson: dict
):
    # Written straight to the database, the way seed data or a manual fix could.
    row = session.get(Lesson, lesson["id"])
    row.kinescope_video_id = ""
    session.add(row)
    session.commit()

    detail = client.get(f"/courses/{course['slug']}/lessons/{lesson['id']}", headers=headers)
    token = client.post(f"/video/{lesson['id']}/token", headers=headers)

    assert detail.json()["video_available"] is False
    assert token.status_code == 409


# ---- download filenames ------------------------------------------------------

def test_filename_turns_newlines_and_tabs_into_single_spaces():
    # A CR/LF left in would end the Content-Disposition header early and let a
    # title write headers of its own.
    assert download_filename("Report\r\nX-Evil: 1", "k.pdf") == "Report X-Evil 1.pdf"
    assert download_filename("Week\t1", "k.pdf") == "Week 1.pdf"


# ---- foreign keys --------------------------------------------------------------

def test_the_test_database_enforces_foreign_keys(session: Session):
    # SQLite skips foreign key checks unless told to, and Postgres never does.
    # Every delete test in the suite is only as honest as this one.
    session.add(Entitlement(user_id=999, course_id=999))

    with pytest.raises(IntegrityError):
        session.commit()


def test_a_never_sold_course_can_be_deleted_after_a_price_change(
    client: TestClient, session: Session, headers: dict, course: dict
):
    client.patch(f"/admin/courses/{course['id']}", json={"price": "3000.00"}, headers=headers)
    assert session.exec(select(PriceAudit)).all()  # the row that used to block it

    res = client.delete(f"/admin/courses/{course['id']}", headers=headers)

    assert res.status_code == 204
    assert session.exec(select(PriceAudit)).all() == []


def test_deleting_a_full_course_clears_every_row_that_points_at_it(
    client: TestClient, session: Session, headers: dict, course: dict, lesson: dict
):
    client.post(
        "/admin/materials",
        json={"title": "Syllabus", "storage_key": new_storage_key("s.pdf"), "course_id": course["id"]},
        headers=headers,
    )
    client.post(
        "/admin/materials",
        json={"title": "Notes", "storage_key": new_storage_key("n.pdf"), "lesson_id": lesson["id"]},
        headers=headers,
    )
    client.patch(f"/admin/courses/{course['id']}", json={"price": "3000.00"}, headers=headers)

    res = client.delete(f"/admin/courses/{course['id']}", headers=headers)

    assert res.status_code == 204
    assert session.exec(select(Course)).all() == []
    assert session.exec(select(Material)).all() == []
    assert session.exec(select(PriceAudit)).all() == []


# ---- unhandled errors ------------------------------------------------------------

def test_an_unhandled_error_is_a_json_500_that_leaks_nothing():
    app = create_app(Settings())
    app.add_api_route("/boom", _boom)

    res = TestClient(app).get("/boom")

    assert res.status_code == 500
    assert res.json() == {"detail": "Internal server error"}
    assert "kaboom" not in res.text
    assert res.headers["X-Request-ID"]


def test_an_unhandled_error_is_logged_with_its_traceback(caplog):
    app = create_app(Settings())
    app.add_api_route("/boom", _boom)

    with caplog.at_level(logging.INFO):
        TestClient(app).get("/boom", headers={"X-Request-ID": "req-500"})

    error = next(r for r in caplog.records if r.levelno == logging.ERROR)
    assert error.exc_info is not None
    assert error.request_id == "req-500"


# ---- request ids and logs -----------------------------------------------------------

def test_a_request_id_is_generated_when_none_is_sent(client: TestClient):
    assert len(client.get("/health").headers["X-Request-ID"]) == 32


def test_a_safe_incoming_request_id_is_kept(client: TestClient):
    res = client.get("/health", headers={"X-Request-ID": "railway-abc.123"})

    assert res.headers["X-Request-ID"] == "railway-abc.123"


def test_an_unsafe_incoming_request_id_is_replaced(client: TestClient):
    res = client.get("/health", headers={"X-Request-ID": 'x" "level": "CRITICAL'})

    assert len(res.headers["X-Request-ID"]) == 32


def test_every_log_line_during_a_request_carries_its_id(caplog):
    app = create_app(Settings())

    def noisy():
        logging.getLogger("oner.test").warning("inside the route")
        return {"ok": True}

    app.add_api_route("/noisy", noisy)

    with caplog.at_level(logging.INFO):
        TestClient(app).get("/noisy", headers={"X-Request-ID": "req-42"})

    ids = {r.name: r.request_id for r in caplog.records if r.name in ("oner.test", "oner.request")}
    assert ids == {"oner.test": "req-42", "oner.request": "req-42"}


def test_the_request_line_records_method_path_status_and_duration(caplog, client: TestClient):
    with caplog.at_level(logging.INFO):
        client.get("/health")

    line = next(r for r in caplog.records if r.name == "oner.request")
    assert (line.method, line.path, line.status) == ("GET", "/health", 200)
    assert line.duration_ms >= 0


def test_log_lines_are_single_line_json():
    record = logging.LogRecord("oner.request", logging.INFO, __file__, 1, "request", None, None)
    record.request_id = "req-1"
    record.method, record.path, record.status, record.duration_ms = "GET", "/health", 200, 1.5

    line = JsonFormatter().format(record)

    assert "\n" not in line
    entry = json.loads(line)
    assert (entry["msg"], entry["request_id"], entry["status"]) == ("request", "req-1", 200)


def test_a_traceback_stays_inside_one_json_line():
    try:
        raise ValueError("bad")
    except ValueError:
        record = logging.LogRecord("x", logging.ERROR, __file__, 1, "boom", None, sys.exc_info())

    line = JsonFormatter().format(record)

    assert "\n" not in line
    assert "ValueError" in json.loads(line)["exc"]


# ---- CORS ---------------------------------------------------------------------------

def _cors_client(origins: list[str]) -> TestClient:
    return TestClient(create_app(Settings(cors_origins=origins)))


def test_an_allowed_origin_can_call_the_api():
    res = _cors_client(["https://oner.kg"]).get("/health", headers={"Origin": "https://oner.kg"})

    assert res.headers["access-control-allow-origin"] == "https://oner.kg"


def test_an_unknown_origin_gets_no_cors_headers():
    res = _cors_client(["https://oner.kg"]).get(
        "/health", headers={"Origin": "https://evil.example"}
    )

    assert "access-control-allow-origin" not in res.headers


def test_no_configured_origins_means_no_cross_origin_access():
    res = _cors_client([]).get("/health", headers={"Origin": "http://localhost:3000"})

    assert "access-control-allow-origin" not in res.headers


def test_preflight_lets_the_admin_page_send_a_bearer_token():
    res = _cors_client(["https://admin.oner.kg"]).options(
        "/admin/courses",
        headers={
            "Origin": "https://admin.oner.kg",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "authorization, content-type",
        },
    )

    assert res.status_code == 200
    assert "PATCH" in res.headers["access-control-allow-methods"]
    assert "authorization" in res.headers["access-control-allow-headers"].lower()


def test_a_browser_can_read_the_request_id():
    res = _cors_client(["https://oner.kg"]).get("/health", headers={"Origin": "https://oner.kg"})

    assert "x-request-id" in res.headers["access-control-expose-headers"].lower()


def test_even_a_500_carries_cors_headers():
    app = create_app(Settings(cors_origins=["https://oner.kg"]))
    app.add_api_route("/boom", _boom)

    res = TestClient(app).get("/boom", headers={"Origin": "https://oner.kg"})

    assert res.status_code == 500
    assert res.headers["access-control-allow-origin"] == "https://oner.kg"
