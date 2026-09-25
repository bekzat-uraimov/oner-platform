"""Day 10 — uploading materials.

The file never passes through this API. An admin asks for a presigned PUT, the
browser sends the bytes straight to R2, and a second call records where they
landed. These tests cover both halves and the seam between them.
"""

from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.security import create_access_token, hash_password
from app.models import Material, MaterialType, User, UserRole
from app.services.authoring import material_type_for
from app.services.entitlements import grant
from app.services.storage import is_material_key, new_storage_key

UPLOAD = "/admin/materials/upload-url"


def _user(session: Session, email: str, role: UserRole = UserRole.student) -> User:
    user = User(email=email, password_hash=hash_password("supersecret123"), role=role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


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
def lesson(client: TestClient, headers: dict, course: dict) -> dict:
    module = client.post(
        f"/admin/courses/{course['id']}/modules", json={"title": "M1"}, headers=headers
    ).json()
    return client.post(
        f"/admin/modules/{module['id']}/lessons", json={"title": "L1"}, headers=headers
    ).json()


# ---- storage keys ---------------------------------------------------------

def test_the_server_picks_the_key_not_the_caller():
    key = new_storage_key("workbook.pdf")

    assert key.startswith("materials/")
    assert key.endswith(".pdf")
    assert "workbook" not in key


def test_two_uploads_of_the_same_filename_get_different_keys():
    assert new_storage_key("notes.pdf") != new_storage_key("notes.pdf")


def test_a_traversing_filename_cannot_escape_the_prefix():
    key = new_storage_key("../../etc/passwd")

    assert key.startswith("materials/")
    assert ".." not in key


def test_a_filename_with_no_extension_still_makes_a_valid_key():
    assert is_material_key(new_storage_key("README"))


def test_keys_we_did_not_issue_are_rejected():
    assert not is_material_key("materials/../secret.pdf")
    assert not is_material_key("other-bucket-path/x.pdf")
    assert not is_material_key("materials/workbook.pdf")


def test_type_is_inferred_from_the_extension():
    assert material_type_for("materials/abc.pdf") == MaterialType.pdf
    assert material_type_for("materials/abc.zip") == MaterialType.zip
    assert material_type_for("materials/abc.mov") == MaterialType.other


# ---- the upload link ------------------------------------------------------

def test_admin_gets_a_presigned_put(client: TestClient, headers: dict):
    res = client.post(UPLOAD, json={"filename": "workbook.pdf"}, headers=headers)

    assert res.status_code == 200
    body = res.json()
    assert body["expires_in"] == 900
    assert is_material_key(body["storage_key"])

    query = parse_qs(urlparse(body["url"]).query)
    assert query["X-Amz-Expires"] == ["900"]
    assert query["X-Amz-Signature"]


def test_the_upload_link_points_at_the_key_it_handed_back(
    client: TestClient, headers: dict
):
    body = client.post(
        UPLOAD, json={"filename": "workbook.pdf"}, headers=headers
    ).json()

    assert body["storage_key"] in urlparse(body["url"]).path


def test_the_upload_link_never_leaks_the_secret_key(client: TestClient, headers: dict):
    res = client.post(UPLOAD, json={"filename": "workbook.pdf"}, headers=headers)

    assert "test-secret-key" not in res.text


def test_students_cannot_get_an_upload_link(client: TestClient, session: Session):
    student = _user(session, "student@oner.kg")

    res = client.post(UPLOAD, json={"filename": "x.pdf"}, headers=_auth(student))

    assert res.status_code == 403


def test_upload_link_requires_authentication(client: TestClient):
    assert client.post(UPLOAD, json={"filename": "x.pdf"}).status_code == 401


def test_unconfigured_storage_returns_503(client: TestClient, headers: dict, storage):
    storage.configured = False

    res = client.post(UPLOAD, json={"filename": "x.pdf"}, headers=headers)

    assert res.status_code == 503


# ---- recording the row ----------------------------------------------------

def test_recording_a_course_material(client: TestClient, headers: dict, course: dict):
    key = client.post(
        UPLOAD, json={"filename": "workbook.pdf"}, headers=headers
    ).json()["storage_key"]

    res = client.post(
        "/admin/materials",
        json={"title": "Workbook", "storage_key": key, "course_id": course["id"]},
        headers=headers,
    )

    assert res.status_code == 201
    assert res.json()["type"] == "pdf"
    assert res.json()["course_id"] == course["id"]


def test_recording_a_lesson_material(client: TestClient, headers: dict, lesson: dict):
    key = new_storage_key("notes.zip")

    res = client.post(
        "/admin/materials",
        json={"title": "Notes", "storage_key": key, "lesson_id": lesson["id"]},
        headers=headers,
    )

    assert res.status_code == 201
    assert res.json()["type"] == "zip"
    assert res.json()["lesson_id"] == lesson["id"]


def test_an_explicit_type_overrides_the_inferred_one(
    client: TestClient, headers: dict, course: dict
):
    res = client.post(
        "/admin/materials",
        json={
            "title": "Reading list",
            "storage_key": new_storage_key("list.pdf"),
            "type": "link",
            "course_id": course["id"],
        },
        headers=headers,
    )

    assert res.json()["type"] == "link"


def test_a_key_we_never_issued_is_refused(
    client: TestClient, session: Session, headers: dict, course: dict
):
    res = client.post(
        "/admin/materials",
        json={
            "title": "Someone else's file",
            "storage_key": "materials/../../secrets.pdf",
            "course_id": course["id"],
        },
        headers=headers,
    )

    assert res.status_code == 400
    assert session.exec(select(Material)).all() == []


def test_a_material_must_attach_to_exactly_one_parent(
    client: TestClient, headers: dict, course: dict, lesson: dict
):
    key = new_storage_key("x.pdf")

    neither = client.post(
        "/admin/materials",
        json={"title": "Orphan", "storage_key": key},
        headers=headers,
    )
    both = client.post(
        "/admin/materials",
        json={
            "title": "Confused",
            "storage_key": key,
            "course_id": course["id"],
            "lesson_id": lesson["id"],
        },
        headers=headers,
    )

    assert neither.status_code == 422
    assert both.status_code == 422


def test_attaching_to_a_course_that_does_not_exist_is_404(
    client: TestClient, headers: dict
):
    res = client.post(
        "/admin/materials",
        json={
            "title": "Nowhere",
            "storage_key": new_storage_key("x.pdf"),
            "course_id": 9999,
        },
        headers=headers,
    )

    assert res.status_code == 404


def test_students_cannot_record_materials(
    client: TestClient, session: Session, course: dict
):
    student = _user(session, "student2@oner.kg")

    res = client.post(
        "/admin/materials",
        json={
            "title": "Mine",
            "storage_key": new_storage_key("x.pdf"),
            "course_id": course["id"],
        },
        headers=_auth(student),
    )

    assert res.status_code == 403


# ---- editing and removing -------------------------------------------------

def test_renaming_a_material_changes_the_download_filename(
    client: TestClient, session: Session, headers: dict, course: dict
):
    material = client.post(
        "/admin/materials",
        json={
            "title": "Draft",
            "storage_key": new_storage_key("wb.pdf"),
            "course_id": course["id"],
        },
        headers=headers,
    ).json()
    buyer = _user(session, "buyer@oner.kg")
    grant(session, buyer.id, course["id"])

    client.patch(
        f"/admin/materials/{material['id']}", json={"title": "Workbook"}, headers=headers
    )
    download = client.get(
        f"/materials/{material['id']}/download", headers=_auth(buyer)
    )

    assert download.json()["filename"] == "Workbook.pdf"


def test_deleting_a_material_makes_the_download_404(
    client: TestClient, session: Session, headers: dict, course: dict
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
    buyer = _user(session, "buyer2@oner.kg")
    grant(session, buyer.id, course["id"])

    assert client.delete(
        f"/admin/materials/{material['id']}", headers=headers
    ).status_code == 204
    assert client.get(
        f"/materials/{material['id']}/download", headers=_auth(buyer)
    ).status_code == 404


def test_unknown_material_is_404(client: TestClient, headers: dict):
    assert client.delete("/admin/materials/9999", headers=headers).status_code == 404
    assert client.patch(
        "/admin/materials/9999", json={"title": "x"}, headers=headers
    ).status_code == 404


# ---- visibility -----------------------------------------------------------

def test_the_admin_course_view_shows_materials_at_both_levels(
    client: TestClient, headers: dict, course: dict, lesson: dict
):
    client.post(
        "/admin/materials",
        json={
            "title": "Syllabus",
            "storage_key": new_storage_key("syllabus.pdf"),
            "course_id": course["id"],
        },
        headers=headers,
    )
    client.post(
        "/admin/materials",
        json={
            "title": "Lesson notes",
            "storage_key": new_storage_key("notes.pdf"),
            "lesson_id": lesson["id"],
        },
        headers=headers,
    )

    view = client.get(f"/admin/courses/{course['id']}", headers=headers).json()

    assert [m["title"] for m in view["materials"]] == ["Syllabus"]
    assert [
        m["title"] for m in view["modules"][0]["lessons"][0]["materials"]
    ] == ["Lesson notes"]


def test_the_public_course_view_shows_no_storage_keys(
    client: TestClient, headers: dict, course: dict
):
    key = new_storage_key("syllabus.pdf")
    client.post(
        "/admin/materials",
        json={"title": "Syllabus", "storage_key": key, "course_id": course["id"]},
        headers=headers,
    )

    assert key not in client.get("/courses/python-basics").text


# ---- the whole upload path ------------------------------------------------

def test_an_admin_uploads_a_workbook_and_an_owner_downloads_it(
    client: TestClient, session: Session, headers: dict, course: dict
):
    # 1. Ask where to put it. The bytes would go straight to R2 from here.
    target = client.post(
        UPLOAD, json={"filename": "workbook.pdf"}, headers=headers
    ).json()

    # 2. Record where they landed.
    material = client.post(
        "/admin/materials",
        json={
            "title": "Workbook",
            "storage_key": target["storage_key"],
            "course_id": course["id"],
        },
        headers=headers,
    ).json()

    # 3. A buyer owns the course.
    buyer = _user(session, "buyer3@oner.kg")
    grant(session, buyer.id, course["id"])

    # 4. And gets a link that expires in a minute — not the 15 the upload had.
    download = client.get(
        f"/materials/{material['id']}/download", headers=_auth(buyer)
    )

    assert download.status_code == 200
    assert download.json()["filename"] == "Workbook.pdf"
    assert download.json()["expires_in"] == 60
    assert target["storage_key"] in urlparse(download.json()["url"]).path


def test_a_non_owner_still_cannot_download_an_uploaded_material(
    client: TestClient, session: Session, headers: dict, course: dict
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
    stranger = _user(session, "stranger@oner.kg")

    res = client.get(
        f"/materials/{material['id']}/download", headers=_auth(stranger)
    )

    assert res.status_code == 403
    assert "X-Amz-Signature" not in res.text
