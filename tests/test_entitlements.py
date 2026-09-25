"""Day 5 — the access core. Ownership is the only thing that unlocks content.

Covered at the service level (grant/has_access/idempotency) and over HTTP
(/me/courses, gated lesson detail, admin manual grant + role gate).
"""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.security import create_access_token, hash_password
from app.models import (
    Course,
    CourseStatus,
    Currency,
    Entitlement,
    Lesson,
    Module,
    User,
    UserRole,
)
from app.services.entitlements import (
    can_access_course,
    grant,
    has_access,
    list_owned_courses,
)


# ---- fixtures / helpers ---------------------------------------------------

def _user(session: Session, email: str, role: UserRole = UserRole.student) -> User:
    user = User(email=email, password_hash=hash_password("supersecret123"), role=role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _course(session: Session, slug: str, *, with_lesson: bool = False) -> Course:
    course = Course(
        title=slug.title(),
        slug=slug,
        price=Decimal("1000.00"),
        currency=Currency.KGS,
        status=CourseStatus.published,
    )
    if with_lesson:
        module = Module(title="M1", order=0)
        module.lessons.append(
            Lesson(title="L1", order=0, duration=60, kinescope_video_id="vid-1")
        )
        course.modules.append(module)
    session.add(course)
    session.commit()
    session.refresh(course)
    return course


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---- service level --------------------------------------------------------

def test_grant_then_has_access(session: Session) -> None:
    user = _user(session, "u@x.com")
    course = _course(session, "c1")
    assert has_access(session, user.id, course.id) is False

    ent = grant(session, user.id, course.id)
    assert ent.id is not None
    assert has_access(session, user.id, course.id) is True


def test_grant_is_idempotent(session: Session) -> None:
    user = _user(session, "u@x.com")
    course = _course(session, "c1")
    first = grant(session, user.id, course.id)
    second = grant(session, user.id, course.id)
    assert first.id == second.id

    rows = session.exec(
        select(Entitlement).where(
            Entitlement.user_id == user.id, Entitlement.course_id == course.id
        )
    ).all()
    assert len(rows) == 1  # never a double-grant


def test_non_owner_blocked(session: Session) -> None:
    owner = _user(session, "owner@x.com")
    other = _user(session, "other@x.com")
    course = _course(session, "c1")
    grant(session, owner.id, course.id)
    assert has_access(session, owner.id, course.id) is True
    assert has_access(session, other.id, course.id) is False


def test_list_owned_returns_only_owned(session: Session) -> None:
    user = _user(session, "u@x.com")
    c1 = _course(session, "c1")
    c2 = _course(session, "c2")
    _course(session, "c3")  # not owned
    grant(session, user.id, c1.id)
    grant(session, user.id, c2.id)

    owned = {c.slug for c in list_owned_courses(session, user.id)}
    assert owned == {"c1", "c2"}


# ---- /me/courses ----------------------------------------------------------

def test_me_courses_requires_auth(client: TestClient) -> None:
    assert client.get("/me/courses").status_code == 401


def test_me_courses_lists_owned(client: TestClient, session: Session) -> None:
    user = _user(session, "u@x.com")
    course = _course(session, "owned")
    _course(session, "not-owned")
    grant(session, user.id, course.id)
    token = create_access_token(user.id)

    resp = client.get("/me/courses", headers=_auth(token))
    assert resp.status_code == 200
    assert {c["slug"] for c in resp.json()} == {"owned"}


def test_me_courses_empty_when_none(client: TestClient, session: Session) -> None:
    user = _user(session, "u@x.com")
    token = create_access_token(user.id)
    resp = client.get("/me/courses", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json() == []


# ---- gated lesson detail --------------------------------------------------

def _lesson_id(session: Session, course: Course) -> int:
    return course.modules[0].lessons[0].id


def test_lesson_detail_blocked_for_non_owner(client: TestClient, session: Session) -> None:
    user = _user(session, "u@x.com")
    course = _course(session, "c1", with_lesson=True)
    lid = _lesson_id(session, course)
    token = create_access_token(user.id)
    resp = client.get(f"/courses/c1/lessons/{lid}", headers=_auth(token))
    assert resp.status_code == 403


def test_lesson_detail_unlocked_for_owner(client: TestClient, session: Session) -> None:
    user = _user(session, "u@x.com")
    course = _course(session, "c1", with_lesson=True)
    lid = _lesson_id(session, course)
    grant(session, user.id, course.id)
    token = create_access_token(user.id)
    resp = client.get(f"/courses/c1/lessons/{lid}", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["video_available"] is True
    assert "kinescope_video_id" not in body  # still no raw id


def test_lesson_detail_admin_bypasses_ownership(client: TestClient, session: Session) -> None:
    admin = _user(session, "a@x.com", role=UserRole.admin)
    course = _course(session, "c1", with_lesson=True)
    lid = _lesson_id(session, course)
    token = create_access_token(admin.id)
    resp = client.get(f"/courses/c1/lessons/{lid}", headers=_auth(token))
    assert resp.status_code == 200


def test_lesson_detail_requires_auth(client: TestClient, session: Session) -> None:
    course = _course(session, "c1", with_lesson=True)
    lid = _lesson_id(session, course)
    assert client.get(f"/courses/c1/lessons/{lid}").status_code == 401


def test_lesson_detail_unknown_course_404(client: TestClient, session: Session) -> None:
    user = _user(session, "u@x.com")
    token = create_access_token(user.id)
    resp = client.get("/courses/nope/lessons/1", headers=_auth(token))
    assert resp.status_code == 404


def test_lesson_detail_lesson_not_in_course_404(client: TestClient, session: Session) -> None:
    user = _user(session, "u@x.com")
    c1 = _course(session, "c1", with_lesson=True)
    other = _course(session, "c2", with_lesson=True)
    grant(session, user.id, c1.id)
    other_lid = _lesson_id(session, other)
    token = create_access_token(user.id)
    # lesson belongs to c2, requested under c1 → 404
    resp = client.get(f"/courses/c1/lessons/{other_lid}", headers=_auth(token))
    assert resp.status_code == 404


# ---- admin manual grant ---------------------------------------------------

def test_admin_grant_gives_access(client: TestClient, session: Session) -> None:
    admin = _user(session, "a@x.com", role=UserRole.admin)
    student = _user(session, "s@x.com")
    course = _course(session, "c1")
    token = create_access_token(admin.id)

    resp = client.post(
        "/admin/entitlements",
        json={"user_id": student.id, "course_id": course.id},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    assert has_access(session, student.id, course.id) is True


def test_admin_grant_idempotent(client: TestClient, session: Session) -> None:
    admin = _user(session, "a@x.com", role=UserRole.admin)
    student = _user(session, "s@x.com")
    course = _course(session, "c1")
    token = create_access_token(admin.id)
    payload = {"user_id": student.id, "course_id": course.id}

    first = client.post("/admin/entitlements", json=payload, headers=_auth(token))
    second = client.post("/admin/entitlements", json=payload, headers=_auth(token))
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


def test_admin_grant_forbidden_for_student(client: TestClient, session: Session) -> None:
    student = _user(session, "s@x.com")
    course = _course(session, "c1")
    token = create_access_token(student.id)
    resp = client.post(
        "/admin/entitlements",
        json={"user_id": student.id, "course_id": course.id},
        headers=_auth(token),
    )
    assert resp.status_code == 403


def test_admin_grant_unknown_user_or_course_404(client: TestClient, session: Session) -> None:
    admin = _user(session, "a@x.com", role=UserRole.admin)
    course = _course(session, "c1")
    token = create_access_token(admin.id)

    bad_user = client.post(
        "/admin/entitlements",
        json={"user_id": 9999, "course_id": course.id},
        headers=_auth(token),
    )
    assert bad_user.status_code == 404

    bad_course = client.post(
        "/admin/entitlements",
        json={"user_id": admin.id, "course_id": 9999},
        headers=_auth(token),
    )
    assert bad_course.status_code == 404


def test_can_access_course_requires_an_entitlement_for_students(session: Session):
    student = _user(session, "student@oner.kg")
    course = _course(session, "gated")

    assert not can_access_course(session, student, course.id)

    grant(session, student.id, course.id)

    assert can_access_course(session, student, course.id)


def test_can_access_course_lets_admins_through_without_owning(session: Session):
    admin = _user(session, "admin@oner.kg", UserRole.admin)
    course = _course(session, "gated-for-admin")

    assert not has_access(session, admin.id, course.id)
    assert can_access_course(session, admin, course.id)
