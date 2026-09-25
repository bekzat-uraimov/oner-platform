"""Day 9 — downloadables, gated by ownership, on links that expire.

There's no DRM for a PDF: once a signed URL leaves our hands it works for anyone
holding it. The defence is that it stops working in a minute.
"""

from decimal import Decimal
from urllib.parse import parse_qs, unquote, urlparse

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.security import create_access_token, hash_password
from app.models import (
    Course,
    CourseStatus,
    Currency,
    Lesson,
    Material,
    MaterialType,
    Module,
    User,
    UserRole,
)
from app.services.entitlements import grant
from app.services.storage import content_disposition, download_filename

PATH = "/materials/{}/download"


# ---- helpers --------------------------------------------------------------

def _user(session: Session, email: str, role: UserRole = UserRole.student) -> User:
    user = User(email=email, password_hash=hash_password("supersecret123"), role=role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _course(
    session: Session, slug: str, *, status: CourseStatus = CourseStatus.published
) -> Course:
    course = Course(
        title=slug.title(),
        slug=slug,
        price=Decimal("2500.00"),
        currency=Currency.KGS,
        status=status,
    )
    module = Module(title="M1", order=0)
    module.lessons.append(Lesson(title="L1", order=0, kinescope_video_id="vid-1"))
    course.modules.append(module)
    session.add(course)
    session.commit()
    session.refresh(course)
    return course


def _material(
    session: Session,
    *,
    course: Course | None = None,
    lesson: Lesson | None = None,
    title: str = "Workbook",
    key: str = "materials/workbook.pdf",
) -> Material:
    material = Material(
        title=title,
        storage_key=key,
        type=MaterialType.pdf,
        course_id=course.id if course else None,
        lesson_id=lesson.id if lesson else None,
    )
    session.add(material)
    session.commit()
    session.refresh(material)
    return material


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


# ---- filename ------------------------------------------------------------

def test_filename_comes_from_the_title_with_the_key_extension():
    assert download_filename("Workbook 1", "materials/abc123.pdf") == "Workbook 1.pdf"


def test_filename_strips_characters_that_would_break_the_header():
    # Quotes would terminate the header value early; slashes would imply a path.
    assert download_filename('Report "Q1"', "x/y.pdf") == "Report Q1.pdf"
    assert download_filename("notes/week1", "x/y.pdf") == "notesweek1.pdf"


def test_filename_keeps_cyrillic():
    assert download_filename("Урок 1", "x/y.pdf") == "Урок 1.pdf"


def test_filename_falls_back_when_the_title_is_all_punctuation():
    assert download_filename("///", "x/y.zip") == "download.zip"


def test_filename_does_not_double_the_extension():
    assert download_filename("notes.pdf", "x/y.pdf") == "notes.pdf"


# ---- the download endpoint ------------------------------------------------

def test_owner_gets_a_signed_url(client: TestClient, session: Session):
    user = _user(session, "owner@oner.kg")
    course = _course(session, "python-basics")
    material = _material(session, course=course)
    grant(session, user.id, course.id)

    res = client.get(PATH.format(material.id), headers=_auth(user))

    assert res.status_code == 200
    body = res.json()
    assert body["filename"] == "Workbook.pdf"
    assert body["expires_in"] == 60

    url = urlparse(body["url"])
    query = parse_qs(url.query)
    assert "oner-test" in url.netloc + url.path
    assert "materials/workbook.pdf" in url.path
    assert query["X-Amz-Expires"] == ["60"]
    assert query["X-Amz-Signature"]


def test_the_url_tells_the_browser_to_save_it_under_the_title(
    client: TestClient, session: Session
):
    user = _user(session, "owner2@oner.kg")
    course = _course(session, "course-2")
    material = _material(session, course=course, title="Cheat Sheet")
    grant(session, user.id, course.id)

    res = client.get(PATH.format(material.id), headers=_auth(user))

    disposition = parse_qs(urlparse(res.json()["url"]).query)
    assert 'filename="Cheat Sheet.pdf"' in unquote(
        disposition["response-content-disposition"][0]
    )


def test_the_signed_url_never_contains_the_secret_key(
    client: TestClient, session: Session
):
    user = _user(session, "owner3@oner.kg")
    course = _course(session, "course-3")
    material = _material(session, course=course)
    grant(session, user.id, course.id)

    res = client.get(PATH.format(material.id), headers=_auth(user))

    assert "test-secret-key" not in res.json()["url"]


def test_material_attached_to_a_lesson_resolves_through_its_course(
    client: TestClient, session: Session
):
    user = _user(session, "owner4@oner.kg")
    course = _course(session, "course-4")
    lesson = course.modules[0].lessons[0]
    material = _material(session, lesson=lesson, title="Lesson notes")
    grant(session, user.id, course.id)

    res = client.get(PATH.format(material.id), headers=_auth(user))

    assert res.status_code == 200


def test_non_owner_gets_403_and_no_url(client: TestClient, session: Session):
    stranger = _user(session, "stranger@oner.kg")
    course = _course(session, "course-5")
    material = _material(session, course=course)

    res = client.get(PATH.format(material.id), headers=_auth(stranger))

    assert res.status_code == 403
    assert "url" not in res.json()
    assert "X-Amz-Signature" not in res.text


def test_admin_downloads_without_owning(client: TestClient, session: Session):
    admin = _user(session, "admin@oner.kg", UserRole.admin)
    course = _course(session, "course-6")
    material = _material(session, course=course)

    res = client.get(PATH.format(material.id), headers=_auth(admin))

    assert res.status_code == 200


def test_unknown_material_is_404(client: TestClient, session: Session):
    user = _user(session, "nobody@oner.kg")

    assert client.get(PATH.format(9999), headers=_auth(user)).status_code == 404


def test_an_owner_keeps_downloading_after_the_course_is_unpublished(
    client: TestClient, session: Session
):
    user = _user(session, "early@oner.kg")
    course = _course(session, "unreleased", status=CourseStatus.draft)
    material = _material(session, course=course)
    grant(session, user.id, course.id)

    assert client.get(PATH.format(material.id), headers=_auth(user)).status_code == 200


def test_unpublished_course_material_is_404_for_a_non_owner(
    client: TestClient, session: Session
):
    user = _user(session, "curious@oner.kg")
    course = _course(session, "unreleased2", status=CourseStatus.draft)
    material = _material(session, course=course)

    assert client.get(PATH.format(material.id), headers=_auth(user)).status_code == 404


def test_a_cyrillic_title_reaches_the_browser_as_the_download_name(
    client: TestClient, session: Session
):
    user = _user(session, "owner9@oner.kg")
    course = _course(session, "course-9")
    material = _material(session, course=course, title="Урок 1")
    grant(session, user.id, course.id)

    res = client.get(PATH.format(material.id), headers=_auth(user))

    raw = parse_qs(urlparse(res.json()["url"]).query)["response-content-disposition"][0]
    assert raw.isascii()  # header values have to be
    assert 'filename="download.pdf"' in raw
    assert unquote(raw.split("filename*=UTF-8''")[1]) == res.json()["filename"]


def test_content_disposition_keeps_ascii_names_as_they_are():
    assert content_disposition("Cheat Sheet.pdf") == 'attachment; filename="Cheat Sheet.pdf"'


def test_content_disposition_never_puts_a_non_ascii_suffix_in_the_fallback():
    assert 'filename="download"' in content_disposition("Файл.тест")


def test_orphaned_material_is_404(client: TestClient, session: Session):
    # Attached to neither a lesson nor a course, so no ownership rule applies.
    user = _user(session, "owner5@oner.kg", UserRole.admin)
    material = _material(session, title="Orphan")

    assert client.get(PATH.format(material.id), headers=_auth(user)).status_code == 404


def test_download_requires_authentication(client: TestClient, session: Session):
    course = _course(session, "course-7")
    material = _material(session, course=course)

    assert client.get(PATH.format(material.id)).status_code == 401


def test_unconfigured_storage_returns_503_not_a_broken_link(
    client: TestClient, session: Session, storage
):
    user = _user(session, "owner6@oner.kg")
    course = _course(session, "course-8")
    material = _material(session, course=course)
    grant(session, user.id, course.id)
    storage.configured = False

    res = client.get(PATH.format(material.id), headers=_auth(user))

    assert res.status_code == 503
