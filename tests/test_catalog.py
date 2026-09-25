"""Day 4: public browses published courses, drafts stay admin-only, and the
browse response never leaks a playable video id."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.security import create_access_token, hash_password
from app.services.catalog import get_lesson_course
from app.services.entitlements import grant
from app.models import (
    Course,
    CourseStatus,
    Currency,
    Lesson,
    Module,
    User,
    UserRole,
)


def _seed_catalog(session: Session) -> None:
    published = Course(
        title="Published Course",
        slug="published",
        description="visible",
        price=Decimal("1000.00"),
        currency=Currency.KGS,
        status=CourseStatus.published,
    )
    module = Module(title="M1", order=0)
    module.lessons.append(
        Lesson(title="L1", order=0, duration=60, kinescope_video_id="vid-secret")
    )
    published.modules.append(module)

    draft = Course(
        title="Draft Course",
        slug="draft",
        price=Decimal("0"),
        currency=Currency.KGS,
        status=CourseStatus.draft,
    )
    session.add(published)
    session.add(draft)
    session.commit()


def _admin_token(session: Session) -> str:
    admin = User(
        email="admin@example.com",
        password_hash=hash_password("supersecret123"),
        role=UserRole.admin,
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return create_access_token(admin.id)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_list_shows_only_published_to_public(client: TestClient, session: Session) -> None:
    _seed_catalog(session)
    resp = client.get("/courses")
    assert resp.status_code == 200
    slugs = {c["slug"] for c in resp.json()}
    assert slugs == {"published"}


def test_list_includes_drafts_for_admin(client: TestClient, session: Session) -> None:
    _seed_catalog(session)
    token = _admin_token(session)
    resp = client.get("/courses", headers=_auth(token))
    assert resp.status_code == 200
    slugs = {c["slug"] for c in resp.json()}
    assert slugs == {"published", "draft"}


def test_detail_returns_structure_without_video_id(
    client: TestClient, session: Session
) -> None:
    _seed_catalog(session)
    resp = client.get("/courses/published")
    assert resp.status_code == 200
    body = resp.json()
    assert body["slug"] == "published"
    assert len(body["modules"]) == 1
    lesson = body["modules"][0]["lessons"][0]
    assert lesson["title"] == "L1"
    # video stays locked — id must not appear in the browse payload
    assert "kinescope_video_id" not in lesson


def test_draft_detail_404_for_public(client: TestClient, session: Session) -> None:
    _seed_catalog(session)
    assert client.get("/courses/draft").status_code == 404


def test_draft_detail_visible_to_admin(client: TestClient, session: Session) -> None:
    _seed_catalog(session)
    token = _admin_token(session)
    resp = client.get("/courses/draft", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["slug"] == "draft"


def test_unknown_slug_404(client: TestClient, session: Session) -> None:
    _seed_catalog(session)
    assert client.get("/courses/does-not-exist").status_code == 404


def test_student_does_not_see_drafts(client: TestClient, session: Session) -> None:
    _seed_catalog(session)
    student = User(
        email="s@example.com",
        password_hash=hash_password("supersecret123"),
        role=UserRole.student,
    )
    session.add(student)
    session.commit()
    session.refresh(student)
    token = create_access_token(student.id)
    resp = client.get("/courses", headers=_auth(token))
    slugs = {c["slug"] for c in resp.json()}
    assert slugs == {"published"}
    assert client.get("/courses/draft", headers=_auth(token)).status_code == 404


def test_get_lesson_course_walks_lesson_to_module_to_course(session: Session):
    _seed_catalog(session)
    lesson = session.exec(select(Lesson)).one()

    course = get_lesson_course(session, lesson.id)

    assert course.slug == "published"


def test_get_lesson_course_returns_none_for_an_unknown_lesson(session: Session):
    _seed_catalog(session)

    assert get_lesson_course(session, 9999) is None


def test_an_owner_still_sees_a_course_after_it_is_unpublished(
    client: TestClient, session: Session
) -> None:
    owner = User(email="owner@example.com", password_hash=hash_password("supersecret123"))
    course = Course(
        title="Retired",
        slug="retired",
        price=Decimal("1000.00"),
        currency=Currency.KGS,
        status=CourseStatus.draft,
    )
    module = Module(title="M1", order=0)
    module.lessons.append(Lesson(title="L1", order=0))
    course.modules.append(module)
    session.add_all([owner, course])
    session.commit()
    grant(session, owner.id, course.id)
    headers = _auth(create_access_token(owner.id))
    lesson_id = course.modules[0].lessons[0].id

    assert client.get("/courses/retired", headers=headers).status_code == 200
    assert client.get(f"/courses/retired/lessons/{lesson_id}", headers=headers).status_code == 200
    # Still out of the catalog, and still hidden from everyone else.
    assert "retired" not in {c["slug"] for c in client.get("/courses", headers=headers).json()}
    assert client.get("/courses/retired").status_code == 404


def test_the_catalog_keeps_a_stable_order(client: TestClient, session: Session) -> None:
    for slug in ("zeta", "alpha", "mid"):
        session.add(
            Course(title=slug, slug=slug, price=Decimal("1"), currency=Currency.KGS, status=CourseStatus.published)
        )
        session.commit()

    assert [c["slug"] for c in client.get("/courses").json()] == ["zeta", "alpha", "mid"]
