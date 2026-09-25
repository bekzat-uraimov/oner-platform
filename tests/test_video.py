"""Day 8 — the watch gate.

Two endpoints, one rule. POST /video/{id}/token decides who may hold a
drmauthtoken; POST /drm/auth is what Kinescope asks on every play before the
decryption key is released.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlmodel import Session, select

from app.core.security import (
    DRM,
    create_access_token,
    create_drm_token,
    decode_token,
    hash_password,
)
from app.core.security import settings as jwt_settings
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
from app.models.base import utcnow
from app.services.entitlements import grant

TOKEN_PATH = "/video/{}/token"
AUTH_PATH = "/drm/auth"
VIDEO_ID = "kine-video-1"


# ---- helpers --------------------------------------------------------------

def _user(session: Session, email: str, role: UserRole = UserRole.student) -> User:
    user = User(email=email, password_hash=hash_password("supersecret123"), role=role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _course_with_lesson(
    session: Session,
    slug: str = "python-basics",
    *,
    video_id: str | None = VIDEO_ID,
    status: CourseStatus = CourseStatus.published,
) -> tuple[Course, Lesson]:
    course = Course(
        title=slug.title(),
        slug=slug,
        price=Decimal("2500.00"),
        currency=Currency.KGS,
        status=status,
    )
    module = Module(title="M1", order=0)
    module.lessons.append(
        Lesson(title="L1", order=0, duration=60, kinescope_video_id=video_id)
    )
    course.modules.append(module)
    session.add(course)
    session.commit()
    session.refresh(course)
    lesson = session.exec(
        select(Lesson).where(Lesson.module_id == course.modules[0].id)
    ).one()
    return course, lesson


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def _play(client: TestClient, token: str | None, video_id: str | None, **kwargs):
    body = {"type": "video", "ip": "11.22.33.0", "user_agent": "Mozilla/5.0"}
    if token is not None:
        body["token"] = token
    if video_id is not None:
        body["id"] = video_id
    return client.post(AUTH_PATH, json=body, **kwargs)


@pytest.fixture
def owner(client: TestClient, session: Session):
    """A student who owns a course with one video lesson."""
    user = _user(session, "owner@oner.kg")
    course, lesson = _course_with_lesson(session)
    grant(session, user.id, course.id)
    return user, course, lesson


# ---- issuing a token ------------------------------------------------------

def test_owner_gets_a_token_and_the_video_id(client: TestClient, owner):
    user, _, lesson = owner

    res = client.post(TOKEN_PATH.format(lesson.id), headers=_auth(user))

    assert res.status_code == 200
    body = res.json()
    assert body["video_id"] == VIDEO_ID
    assert body["expires_in"] == 600
    assert body["drm_auth_token"]


def test_the_token_is_typed_and_bound_to_one_video(client: TestClient, owner):
    user, _, lesson = owner

    res = client.post(TOKEN_PATH.format(lesson.id), headers=_auth(user))

    payload = decode_token(res.json()["drm_auth_token"])
    assert payload["type"] == DRM
    assert payload["sub"] == str(user.id)
    assert payload["vid"] == VIDEO_ID


def test_non_owner_gets_403_and_no_token(client: TestClient, session: Session, owner):
    _, _, lesson = owner
    stranger = _user(session, "stranger@oner.kg")

    res = client.post(TOKEN_PATH.format(lesson.id), headers=_auth(stranger))

    assert res.status_code == 403
    assert "drm_auth_token" not in res.json()
    assert VIDEO_ID not in res.text


def test_admin_gets_a_token_without_owning(client: TestClient, session: Session, owner):
    _, course, lesson = owner
    admin = _user(session, "admin@oner.kg", UserRole.admin)
    assert session.exec(
        select(Entitlement).where(Entitlement.user_id == admin.id)
    ).all() == []

    res = client.post(TOKEN_PATH.format(lesson.id), headers=_auth(admin))

    assert res.status_code == 200


def test_unknown_lesson_is_404(client: TestClient, session: Session):
    user = _user(session, "nobody@oner.kg")

    res = client.post(TOKEN_PATH.format(9999), headers=_auth(user))

    assert res.status_code == 404


def test_lesson_without_a_video_is_409_for_the_owner(
    client: TestClient, session: Session
):
    user = _user(session, "owner2@oner.kg")
    course, lesson = _course_with_lesson(session, "no-footage", video_id=None)
    grant(session, user.id, course.id)

    res = client.post(TOKEN_PATH.format(lesson.id), headers=_auth(user))

    assert res.status_code == 409


def test_an_owner_keeps_watching_after_the_course_is_unpublished(
    client: TestClient, session: Session
):
    # Unpublishing takes a course out of the catalog, not away from its buyers.
    user = _user(session, "early@oner.kg")
    course, lesson = _course_with_lesson(session, "unreleased", status=CourseStatus.draft)
    grant(session, user.id, course.id)

    res = client.post(TOKEN_PATH.format(lesson.id), headers=_auth(user))

    assert res.status_code == 200


def test_an_unpublished_course_is_404_for_a_student_who_does_not_own_it(
    client: TestClient, session: Session
):
    user = _user(session, "curious@oner.kg")
    _, lesson = _course_with_lesson(session, "unreleased3", status=CourseStatus.draft)

    assert client.post(TOKEN_PATH.format(lesson.id), headers=_auth(user)).status_code == 404


def test_draft_course_is_visible_to_an_admin(client: TestClient, session: Session):
    admin = _user(session, "admin2@oner.kg", UserRole.admin)
    _, lesson = _course_with_lesson(session, "unreleased2", status=CourseStatus.draft)

    res = client.post(TOKEN_PATH.format(lesson.id), headers=_auth(admin))

    assert res.status_code == 200


def test_token_endpoint_requires_authentication(client: TestClient, owner):
    _, _, lesson = owner

    assert client.post(TOKEN_PATH.format(lesson.id)).status_code == 401


# ---- Kinescope's playback check -------------------------------------------

def test_valid_token_releases_the_key(client: TestClient, owner):
    user, _, _ = owner

    res = _play(client, create_drm_token(user.id, VIDEO_ID), VIDEO_ID)

    assert res.status_code == 200


def test_a_token_for_one_video_cannot_play_another(
    client: TestClient, session: Session, owner
):
    # Buy the cheap course, then try its token against a course you don't own.
    user, _, _ = owner
    _course_with_lesson(session, "premium", video_id="kine-video-premium")

    res = _play(client, create_drm_token(user.id, VIDEO_ID), "kine-video-premium")

    assert res.status_code == 403


def test_a_video_reused_in_two_courses_plays_if_you_own_either(
    client: TestClient, session: Session
):
    # A shared intro lesson can sit in more than one course. Owning the second
    # one must be enough, even though the first is found first.
    shared = "kine-shared-intro"
    _course_with_lesson(session, "course-a", video_id=shared)
    course_b, _ = _course_with_lesson(session, "course-b", video_id=shared)
    user = _user(session, "owns-b@oner.kg")
    grant(session, user.id, course_b.id)

    res = _play(client, create_drm_token(user.id, shared), shared)

    assert res.status_code == 200


def test_an_access_token_is_not_a_playback_key(client: TestClient, owner):
    user, _, _ = owner

    res = _play(client, create_access_token(user.id), VIDEO_ID)

    assert res.status_code == 403


def test_garbage_token_is_denied(client: TestClient, owner):
    assert _play(client, "not-a-jwt", VIDEO_ID).status_code == 403


def test_expired_token_is_denied(client: TestClient, owner):
    user, _, _ = owner
    past = utcnow() - timedelta(minutes=1)
    expired = jwt.encode(
        {"sub": str(user.id), "type": DRM, "vid": VIDEO_ID, "exp": past},
        jwt_settings.jwt_secret,
        algorithm=jwt_settings.jwt_algorithm,
    )

    assert _play(client, expired, VIDEO_ID).status_code == 403


def test_unknown_video_is_denied(client: TestClient, owner):
    user, _, _ = owner

    res = _play(client, create_drm_token(user.id, "kine-ghost"), "kine-ghost")

    assert res.status_code == 403


def test_revoking_the_entitlement_stops_playback_within_the_token_ttl(
    client: TestClient, session: Session, owner
):
    # Ownership is re-read on every play, so a refund takes effect immediately
    # rather than waiting for the token to expire.
    user, course, _ = owner
    token = create_drm_token(user.id, VIDEO_ID)
    assert _play(client, token, VIDEO_ID).status_code == 200

    entitlement = session.exec(
        select(Entitlement).where(Entitlement.user_id == user.id)
    ).one()
    session.delete(entitlement)
    session.commit()

    assert _play(client, token, VIDEO_ID).status_code == 403


def test_deleted_user_cannot_play(client: TestClient, session: Session, owner):
    user, _, _ = owner
    token = create_drm_token(user.id, VIDEO_ID)
    session.delete(session.exec(select(Entitlement)).one())
    session.delete(session.get(User, user.id))
    session.commit()

    assert _play(client, token, VIDEO_ID).status_code == 403


def test_missing_token_is_400(client: TestClient, owner):
    assert _play(client, None, VIDEO_ID).status_code == 400


def test_missing_video_id_is_400(client: TestClient, owner):
    user, _, _ = owner

    assert _play(client, create_drm_token(user.id, VIDEO_ID), None).status_code == 400


# ---- Basic Auth on the callback -------------------------------------------

def test_callback_is_open_when_basic_auth_is_not_configured(client: TestClient, owner):
    user, _, _ = owner

    assert _play(client, create_drm_token(user.id, VIDEO_ID), VIDEO_ID).status_code == 200


def test_configured_basic_auth_rejects_wrong_credentials(
    client: TestClient, settings, owner
):
    user, _, _ = owner
    settings.kinescope_drm_auth_user = "kinescope"
    settings.kinescope_drm_auth_password = "s3cret"

    res = _play(
        client,
        create_drm_token(user.id, VIDEO_ID),
        VIDEO_ID,
        auth=("kinescope", "wrong"),
    )

    assert res.status_code == 401


def test_configured_basic_auth_rejects_missing_credentials(
    client: TestClient, settings, owner
):
    user, _, _ = owner
    settings.kinescope_drm_auth_user = "kinescope"
    settings.kinescope_drm_auth_password = "s3cret"

    assert _play(client, create_drm_token(user.id, VIDEO_ID), VIDEO_ID).status_code == 401


def test_configured_basic_auth_accepts_the_right_credentials(
    client: TestClient, settings, owner
):
    user, _, _ = owner
    settings.kinescope_drm_auth_user = "kinescope"
    settings.kinescope_drm_auth_password = "s3cret"

    res = _play(
        client,
        create_drm_token(user.id, VIDEO_ID),
        VIDEO_ID,
        auth=("kinescope", "s3cret"),
    )

    assert res.status_code == 200
