"""Day 10 — the admin write path.

Until now nothing in the API could create a course; app/seed.py was the only
way content existed. These are the routes an admin page drives.
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.security import create_access_token, hash_password
from app.models import (
    Course,
    CourseStatus,
    Currency,
    Lesson,
    Material,
    MaterialType,
    Module,
    PriceAudit,
    Purchase,
    User,
    UserRole,
)
from app.services.entitlements import grant


def _user(session: Session, email: str, role: UserRole = UserRole.student) -> User:
    user = User(email=email, password_hash=hash_password("supersecret123"), role=role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


@pytest.fixture
def admin(session: Session) -> User:
    return _user(session, "admin@oner.kg", UserRole.admin)


@pytest.fixture
def headers(admin: User) -> dict:
    return _auth(admin)


@pytest.fixture
def course(client: TestClient, headers: dict) -> dict:
    res = client.post(
        "/admin/courses",
        json={"title": "Python Basics", "slug": "python-basics", "price": "2500.00"},
        headers=headers,
    )
    assert res.status_code == 201
    return res.json()


# ---- courses --------------------------------------------------------------

def test_admin_creates_a_course(course):
    assert course["slug"] == "python-basics"
    assert course["modules"] == []


def test_a_new_course_starts_as_a_draft(course):
    # Publishing is a second, deliberate step — a half-built course must not be
    # buyable the moment it's created.
    assert course["status"] == "draft"


def test_a_draft_course_is_invisible_to_the_public(client: TestClient, course):
    assert client.get("/courses").json() == []


def test_publishing_puts_the_course_in_the_public_catalog(
    client: TestClient, headers: dict, course
):
    client.patch(
        f"/admin/courses/{course['id']}", json={"status": "published"}, headers=headers
    )

    assert [c["slug"] for c in client.get("/courses").json()] == ["python-basics"]


def test_duplicate_slug_is_a_409(client: TestClient, headers: dict, course):
    res = client.post(
        "/admin/courses",
        json={"title": "Another", "slug": "python-basics"},
        headers=headers,
    )

    assert res.status_code == 409


def test_slug_must_be_url_safe(client: TestClient, headers: dict):
    res = client.post(
        "/admin/courses",
        json={"title": "Bad", "slug": "Python Basics!"},
        headers=headers,
    )

    assert res.status_code == 422


def test_unknown_course_is_404(client: TestClient, headers: dict):
    assert client.get("/admin/courses/9999", headers=headers).status_code == 404


def test_renaming_onto_a_taken_slug_is_a_409(
    client: TestClient, session: Session, headers: dict, course
):
    other = client.post(
        "/admin/courses",
        json={"title": "Other", "slug": "other-course"},
        headers=headers,
    ).json()

    res = client.patch(
        f"/admin/courses/{other['id']}", json={"slug": "python-basics"}, headers=headers
    )

    assert res.status_code == 409
    # The rejected rename left both courses on their original slugs.
    session.expire_all()
    assert session.get(Course, other["id"]).slug == "other-course"
    assert session.get(Course, course["id"]).slug == "python-basics"


def test_a_rejected_rename_writes_no_audit_row(
    client: TestClient, session: Session, headers: dict, course
):
    # The price change and the slug collision share one transaction, so the
    # audit row must roll back with the rename that failed.
    other = client.post(
        "/admin/courses", json={"title": "Other", "slug": "other-2"}, headers=headers
    ).json()

    client.patch(
        f"/admin/courses/{other['id']}",
        json={"slug": "python-basics", "price": "9999.00"},
        headers=headers,
    )

    assert session.exec(select(PriceAudit)).all() == []


# ---- price audit ----------------------------------------------------------

def test_a_price_change_writes_an_audit_row(
    client: TestClient, session: Session, headers: dict, admin: User, course
):
    client.patch(
        f"/admin/courses/{course['id']}", json={"price": "3500.00"}, headers=headers
    )

    audit = session.exec(select(PriceAudit)).one()
    assert audit.old_price == Decimal("2500.00")
    assert audit.new_price == Decimal("3500.00")
    assert audit.changed_by == admin.id


def test_editing_something_else_writes_no_audit_row(
    client: TestClient, session: Session, headers: dict, course
):
    client.patch(
        f"/admin/courses/{course['id']}", json={"title": "Renamed"}, headers=headers
    )

    assert session.exec(select(PriceAudit)).all() == []


def test_resaving_the_same_price_writes_no_audit_row(
    client: TestClient, session: Session, headers: dict, course
):
    client.patch(
        f"/admin/courses/{course['id']}", json={"price": "2500.00"}, headers=headers
    )

    assert session.exec(select(PriceAudit)).all() == []


# ---- modules and lessons --------------------------------------------------

def test_modules_and_lessons_append_in_order(
    client: TestClient, headers: dict, course
):
    first = client.post(
        f"/admin/courses/{course['id']}/modules",
        json={"title": "Getting started"},
        headers=headers,
    ).json()
    second = client.post(
        f"/admin/courses/{course['id']}/modules",
        json={"title": "Hooks"},
        headers=headers,
    ).json()

    assert [first["order"], second["order"]] == [0, 1]

    lessons = [
        client.post(
            f"/admin/modules/{first['id']}/lessons",
            json={"title": title},
            headers=headers,
        ).json()
        for title in ("Variables", "Loops")
    ]
    assert [lesson["order"] for lesson in lessons] == [0, 1]


def test_an_explicit_order_is_respected(client: TestClient, headers: dict, course):
    module = client.post(
        f"/admin/courses/{course['id']}/modules",
        json={"title": "Intro", "order": 7},
        headers=headers,
    ).json()

    assert module["order"] == 7


def test_attaching_a_kinescope_video_to_a_lesson(
    client: TestClient, headers: dict, course
):
    module = client.post(
        f"/admin/courses/{course['id']}/modules",
        json={"title": "M1"},
        headers=headers,
    ).json()
    lesson = client.post(
        f"/admin/modules/{module['id']}/lessons",
        json={"title": "Variables"},
        headers=headers,
    ).json()
    assert lesson["kinescope_video_id"] is None

    res = client.patch(
        f"/admin/lessons/{lesson['id']}",
        json={"kinescope_video_id": "kine-abc-1"},
        headers=headers,
    )

    assert res.status_code == 200
    assert res.json()["kinescope_video_id"] == "kine-abc-1"


def test_the_admin_view_shows_video_ids_the_public_one_hides(
    client: TestClient, session: Session, headers: dict, course
):
    module = client.post(
        f"/admin/courses/{course['id']}/modules", json={"title": "M1"}, headers=headers
    ).json()
    client.post(
        f"/admin/modules/{module['id']}/lessons",
        json={"title": "Variables", "kinescope_video_id": "kine-abc-1"},
        headers=headers,
    )
    client.patch(
        f"/admin/courses/{course['id']}", json={"status": "published"}, headers=headers
    )

    admin_view = client.get(f"/admin/courses/{course['id']}", headers=headers)
    public_view = client.get("/courses/python-basics")

    assert "kine-abc-1" in admin_view.text
    assert "kine-abc-1" not in public_view.text


# ---- deletion -------------------------------------------------------------

def test_deleting_a_course_takes_its_modules_and_lessons(
    client: TestClient, session: Session, headers: dict, course
):
    module = client.post(
        f"/admin/courses/{course['id']}/modules", json={"title": "M1"}, headers=headers
    ).json()
    client.post(
        f"/admin/modules/{module['id']}/lessons", json={"title": "L1"}, headers=headers
    )

    res = client.delete(f"/admin/courses/{course['id']}", headers=headers)

    assert res.status_code == 204
    assert session.exec(select(Course)).all() == []
    assert session.exec(select(Module)).all() == []
    assert session.exec(select(Lesson)).all() == []


def test_deleting_a_lesson_drops_its_material_rows(
    client: TestClient, session: Session, headers: dict, course
):
    module = client.post(
        f"/admin/courses/{course['id']}/modules", json={"title": "M1"}, headers=headers
    ).json()
    lesson = client.post(
        f"/admin/modules/{module['id']}/lessons", json={"title": "L1"}, headers=headers
    ).json()
    session.add(
        Material(
            lesson_id=lesson["id"],
            title="Notes",
            storage_key="materials/notes.pdf",
            type=MaterialType.pdf,
        )
    )
    session.commit()

    res = client.delete(f"/admin/lessons/{lesson['id']}", headers=headers)

    assert res.status_code == 204
    assert session.exec(select(Material)).all() == []


def test_renaming_and_reordering_a_module(client: TestClient, headers: dict, course):
    module = client.post(
        f"/admin/courses/{course['id']}/modules", json={"title": "M1"}, headers=headers
    ).json()

    res = client.patch(
        f"/admin/modules/{module['id']}",
        json={"title": "Getting started", "order": 3},
        headers=headers,
    )

    assert res.status_code == 200
    assert res.json()["title"] == "Getting started"
    assert res.json()["order"] == 3


def test_deleting_a_module_takes_its_lessons_and_their_materials(
    client: TestClient, session: Session, headers: dict, course
):
    module = client.post(
        f"/admin/courses/{course['id']}/modules", json={"title": "M1"}, headers=headers
    ).json()
    lesson = client.post(
        f"/admin/modules/{module['id']}/lessons", json={"title": "L1"}, headers=headers
    ).json()
    session.add(
        Material(
            lesson_id=lesson["id"],
            title="Notes",
            storage_key="materials/notes.pdf",
            type=MaterialType.pdf,
        )
    )
    session.commit()

    res = client.delete(f"/admin/modules/{module['id']}", headers=headers)

    assert res.status_code == 204
    assert session.exec(select(Module)).all() == []
    assert session.exec(select(Lesson)).all() == []
    assert session.exec(select(Material)).all() == []


def test_a_purchased_course_cannot_be_deleted(
    client: TestClient, session: Session, headers: dict, course
):
    buyer = _user(session, "buyer@oner.kg")
    grant(session, buyer.id, course["id"])

    res = client.delete(f"/admin/courses/{course['id']}", headers=headers)

    assert res.status_code == 409
    assert session.get(Course, course["id"]) is not None


def test_an_abandoned_checkout_also_blocks_deletion(
    client: TestClient, session: Session, headers: dict, course
):
    # A pending purchase is the conversion record, and its foreign key would
    # break the delete anyway.
    buyer = _user(session, "abandoner@oner.kg")
    session.add(
        Purchase(
            user_id=buyer.id,
            course_id=course["id"],
            amount=Decimal("2500.00"),
            currency=Currency.KGS,
        )
    )
    session.commit()

    assert client.delete(
        f"/admin/courses/{course['id']}", headers=headers
    ).status_code == 409


# ---- authorization --------------------------------------------------------

def test_students_cannot_author(client: TestClient, session: Session):
    student = _user(session, "student@oner.kg")

    res = client.post(
        "/admin/courses",
        json={"title": "Mine now", "slug": "mine-now"},
        headers=_auth(student),
    )

    assert res.status_code == 403


def test_authoring_requires_authentication(client: TestClient):
    assert client.post(
        "/admin/courses", json={"title": "Anon", "slug": "anon"}
    ).status_code == 401


def test_a_student_cannot_publish_a_course(
    client: TestClient, session: Session, course
):
    student = _user(session, "student2@oner.kg")

    res = client.patch(
        f"/admin/courses/{course['id']}",
        json={"status": "published"},
        headers=_auth(student),
    )

    assert res.status_code == 403


def test_a_student_cannot_read_video_ids_through_the_admin_view(
    client: TestClient, session: Session, course
):
    student = _user(session, "student3@oner.kg")

    res = client.get(f"/admin/courses/{course['id']}", headers=_auth(student))

    assert res.status_code == 403


# ---- the authoring path end to end ----------------------------------------

def test_an_admin_builds_a_sellable_course_from_nothing(
    client: TestClient, session: Session, headers: dict
):
    """The sequence an admin page walks: course, module, lesson, video, publish."""
    course = client.post(
        "/admin/courses",
        json={
            "title": "Frontend with React",
            "slug": "frontend-react",
            "price": "4990.00",
            "currency": "KGS",
        },
        headers=headers,
    ).json()

    module = client.post(
        f"/admin/courses/{course['id']}/modules",
        json={"title": "Getting started"},
        headers=headers,
    ).json()

    lesson = client.post(
        f"/admin/modules/{module['id']}/lessons",
        json={"title": "Why React", "duration": 420},
        headers=headers,
    ).json()

    # The video is uploaded to Kinescope out of band, then attached by id.
    client.patch(
        f"/admin/lessons/{lesson['id']}",
        json={"kinescope_video_id": "kine-react-1"},
        headers=headers,
    )

    client.patch(
        f"/admin/courses/{course['id']}", json={"status": "published"}, headers=headers
    )

    # A buyer can now find it, and it costs what the admin set.
    listing = client.get("/courses").json()
    assert [c["slug"] for c in listing] == ["frontend-react"]
    assert listing[0]["price"] == "4990.00"

    # And owning it releases the video the catalog never showed.
    buyer = _user(session, "buyer2@oner.kg")
    grant(session, buyer.id, course["id"])
    token = client.post(f"/video/{lesson['id']}/token", headers=_auth(buyer))

    assert token.status_code == 200
    assert token.json()["video_id"] == "kine-react-1"
