"""Keeping R2 from filling up with files nothing points at. Every stored file
is paid for; a dead one is a bill for nothing.

R2 is stubbed at the boto3 client, so these tests check the exact requests the
app sends and never touch the network.
"""

import logging
from datetime import datetime, timedelta, timezone

import pytest
from botocore.stub import Stubber
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.security import create_access_token, hash_password
from app.models import Material, User, UserRole
from app.services.cleanup import reclaim
from app.services.storage import R2Client, new_storage_key

BUCKET = "oner-test"
OLD = datetime.now(timezone.utc) - timedelta(days=3)
FRESH = datetime.now(timezone.utc) - timedelta(minutes=5)


def _expect_delete(r2: Stubber, keys: list[str], refused=()) -> None:
    r2.add_response(
        "delete_objects",
        {"Errors": [{"Key": key, "Code": "AccessDenied", "Message": "denied"} for key in refused]},
        expected_params={
            "Bucket": BUCKET,
            "Delete": {"Objects": [{"Key": key} for key in keys], "Quiet": True},
        },
    )


def _expect_listing(r2: Stubber, objects, *, token=None, next_token=None) -> None:
    params = {"Bucket": BUCKET, "Prefix": "materials/"}
    if token is not None:
        params["ContinuationToken"] = token
    response = {
        "Contents": [{"Key": key, "LastModified": modified} for key, modified in objects],
        "IsTruncated": next_token is not None,
    }
    if next_token is not None:
        response["NextContinuationToken"] = next_token
    r2.add_response("list_objects_v2", response, expected_params=params)


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
        "/admin/courses", json={"title": "T", "slug": "t", "status": "published"}, headers=headers
    ).json()


@pytest.fixture
def lesson(client: TestClient, headers: dict, course: dict) -> dict:
    module = client.post(
        f"/admin/courses/{course['id']}/modules", json={"title": "Day 1"}, headers=headers
    ).json()
    return client.post(
        f"/admin/modules/{module['id']}/lessons", json={"title": "L1"}, headers=headers
    ).json()


def _material(client: TestClient, headers: dict, **parent) -> dict:
    return client.post(
        "/admin/materials",
        json={"title": "Workbook", "storage_key": new_storage_key("wb.pdf"), **parent},
        headers=headers,
    ).json()


# ---- deleting content deletes its files --------------------------------------

def test_deleting_a_material_deletes_its_file(
    client: TestClient, headers: dict, course: dict, r2: Stubber
):
    material = _material(client, headers, course_id=course["id"])
    _expect_delete(r2, [material["storage_key"]])

    res = client.delete(f"/admin/materials/{material['id']}", headers=headers)

    assert res.status_code == 204
    r2.assert_no_pending_responses()


def test_deleting_a_lesson_deletes_all_its_files_in_one_request(
    client: TestClient, headers: dict, lesson: dict, r2: Stubber
):
    keys = [_material(client, headers, lesson_id=lesson["id"])["storage_key"] for _ in range(2)]
    _expect_delete(r2, keys)

    client.delete(f"/admin/lessons/{lesson['id']}", headers=headers)

    r2.assert_no_pending_responses()


def test_deleting_a_module_deletes_its_lessons_files(
    client: TestClient, headers: dict, lesson: dict, r2: Stubber
):
    key = _material(client, headers, lesson_id=lesson["id"])["storage_key"]
    _expect_delete(r2, [key])

    client.delete(f"/admin/modules/{lesson['module_id']}", headers=headers)

    r2.assert_no_pending_responses()


def test_deleting_a_course_deletes_course_and_lesson_files_together(
    client: TestClient, headers: dict, course: dict, lesson: dict, r2: Stubber
):
    course_key = _material(client, headers, course_id=course["id"])["storage_key"]
    lesson_key = _material(client, headers, lesson_id=lesson["id"])["storage_key"]
    _expect_delete(r2, [course_key, lesson_key])

    client.delete(f"/admin/courses/{course['id']}", headers=headers)

    r2.assert_no_pending_responses()


def test_deleting_something_with_no_files_makes_no_storage_call(
    client: TestClient, headers: dict, lesson: dict, caplog
):
    with caplog.at_level(logging.WARNING, logger="oner.storage"):
        res = client.delete(f"/admin/lessons/{lesson['id']}", headers=headers)

    assert res.status_code == 204
    # An unexpected call would have hit the stubber and been logged as a failure.
    assert not [r for r in caplog.records if r.name == "oner.storage"]


def test_a_storage_failure_does_not_fail_the_delete(
    client: TestClient, session: Session, headers: dict, course: dict, r2: Stubber, caplog
):
    material = _material(client, headers, course_id=course["id"])
    r2.add_client_error("delete_objects", service_error_code="AccessDenied", http_status_code=403)

    with caplog.at_level(logging.WARNING, logger="oner.storage"):
        res = client.delete(f"/admin/materials/{material['id']}", headers=headers)

    assert res.status_code == 204
    assert session.exec(select(Material)).all() == []
    assert any("leaving them to the sweep" in r.getMessage() for r in caplog.records)


def test_files_r2_refuses_to_delete_are_logged(storage: R2Client, r2: Stubber, caplog):
    _expect_delete(r2, ["materials/a.pdf"], refused=["materials/a.pdf"])

    with caplog.at_level(logging.WARNING, logger="oner.storage"):
        reclaim(storage, ["materials/a.pdf"])

    assert any("materials/a.pdf" in r.getMessage() for r in caplog.records)


def test_reclaim_without_r2_configured_does_nothing(storage: R2Client, r2: Stubber, caplog):
    storage.configured = False

    with caplog.at_level(logging.WARNING, logger="oner.storage"):
        reclaim(storage, ["materials/a.pdf"])

    assert not [r for r in caplog.records if r.name == "oner.storage"]


def test_big_deletes_are_split_into_batches_of_1000(storage: R2Client, r2: Stubber):
    keys = [f"materials/{i:032x}.pdf" for i in range(1500)]
    _expect_delete(r2, keys[:1000])
    _expect_delete(r2, keys[1000:])

    assert storage.delete_objects(keys) == []
    r2.assert_no_pending_responses()


def test_recording_the_same_upload_twice_is_a_409(client: TestClient, headers: dict, course: dict):
    # Two rows on one file would mean deleting either row deletes the other's file.
    body = {"title": "Workbook", "storage_key": new_storage_key("wb.pdf"), "course_id": course["id"]}

    assert client.post("/admin/materials", json=body, headers=headers).status_code == 201
    assert client.post("/admin/materials", json=body, headers=headers).status_code == 409


# ---- the sweep -------------------------------------------------------------------

def test_a_dry_run_reports_old_orphans_and_deletes_nothing(
    client: TestClient, headers: dict, course: dict, r2: Stubber
):
    kept = _material(client, headers, course_id=course["id"])["storage_key"]
    orphan = new_storage_key("old.pdf")
    uploading = new_storage_key("new.pdf")  # uploaded minutes ago, not recorded yet
    _expect_listing(r2, [(kept, OLD), (orphan, OLD), (uploading, FRESH)])

    res = client.post("/admin/storage/sweep", headers=headers)

    assert res.json() == {
        "scanned": 3,
        "orphan_count": 1,
        "orphans": [orphan],
        "deleted": 0,
        "applied": False,
    }
    r2.assert_no_pending_responses()


def test_applying_the_sweep_deletes_only_old_orphans(
    client: TestClient, headers: dict, course: dict, r2: Stubber
):
    kept = _material(client, headers, course_id=course["id"])["storage_key"]
    orphan = new_storage_key("old.pdf")
    uploading = new_storage_key("new.pdf")
    _expect_listing(r2, [(kept, OLD), (orphan, OLD), (uploading, FRESH)])
    _expect_delete(r2, [orphan])

    res = client.post("/admin/storage/sweep", params={"apply": "true"}, headers=headers)

    assert (res.json()["deleted"], res.json()["applied"]) == (1, True)
    r2.assert_no_pending_responses()


def test_the_sweep_reads_every_page_of_the_bucket(client: TestClient, headers: dict, r2: Stubber):
    first, second = new_storage_key("a.pdf"), new_storage_key("b.pdf")
    _expect_listing(r2, [(first, OLD)], next_token="page-2")
    _expect_listing(r2, [(second, OLD)], token="page-2")

    res = client.post("/admin/storage/sweep", headers=headers)

    assert res.json()["orphans"] == [first, second]


def test_the_report_lists_100_orphans_but_counts_all(
    client: TestClient, headers: dict, r2: Stubber
):
    _expect_listing(r2, [(new_storage_key(f"{i}.pdf"), OLD) for i in range(150)])

    body = client.post("/admin/storage/sweep", headers=headers).json()

    assert (body["orphan_count"], len(body["orphans"])) == (150, 100)


def test_sweep_without_r2_configured_is_a_503(client: TestClient, headers: dict, storage: R2Client):
    storage.configured = False

    assert client.post("/admin/storage/sweep", headers=headers).status_code == 503


def test_sweep_when_r2_errors_is_a_502(client: TestClient, headers: dict, r2: Stubber):
    r2.add_client_error("list_objects_v2", service_error_code="AccessDenied", http_status_code=403)

    assert client.post("/admin/storage/sweep", headers=headers).status_code == 502


def test_students_cannot_sweep(client: TestClient, session: Session):
    student = _user(session, "student@oner.kg")

    assert client.post("/admin/storage/sweep", headers=_auth(student)).status_code == 403
