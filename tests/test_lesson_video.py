"""Day 13 — a lesson's video from the admin page: upload straight to Kinescope,
wait for processing, swap it in, and delete what nothing plays any more.

Kinescope is faked behind httpx.MockTransport (FakeKinescope in conftest), so
the real client builds real requests and nothing leaves the process.
"""

import json
import logging

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.security import create_access_token, hash_password
from app.models import User, UserRole
from app.services.entitlements import grant
from app.services.kinescope import KinescopeClient, KinescopeError, KinescopeNotConfigured
from app.services.lesson_video import delete_videos
from tests.conftest import FakeKinescope

UPLOAD = {"filename": "variables.mp4", "filesize": 1_048_576}
HOOK_AUTH = ("kinescope", "hook-secret")


def _user(session: Session, email: str, role: UserRole = UserRole.student) -> User:
    user = User(email=email, password_hash=hash_password("supersecret123"), role=role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def _hook(video_id: str, status: str = "done", event: str = "media.update.status") -> dict:
    return {"event": event, "data": {"id": video_id, "status": status}}


@pytest.fixture
def headers(session: Session) -> dict:
    return _auth(_user(session, "admin@oner.kg", UserRole.admin))


@pytest.fixture
def course(client: TestClient, headers: dict) -> dict:
    return client.post(
        "/admin/courses",
        json={"title": "Python Backend", "slug": "python-backend", "price": "6990.00", "status": "published"},
        headers=headers,
    ).json()


@pytest.fixture
def module(client: TestClient, headers: dict, course: dict) -> dict:
    return client.post(
        f"/admin/courses/{course['id']}/modules", json={"title": "Python Foundations"}, headers=headers
    ).json()


@pytest.fixture
def lesson(client: TestClient, headers: dict, module: dict) -> dict:
    return client.post(
        f"/admin/modules/{module['id']}/lessons", json={"title": "Variables"}, headers=headers
    ).json()


@pytest.fixture
def owner(session: Session, course: dict) -> dict:
    user = _user(session, "owner@oner.kg")
    grant(session, user.id, course["id"])
    return _auth(user)


@pytest.fixture
def webhook_on(settings):
    settings.kinescope_webhook_user, settings.kinescope_webhook_password = HOOK_AUTH


def _lesson_with_video(client, headers, module, kinescope_api, video_id, title="Functions") -> dict:
    kinescope_api.videos[video_id] = {"status": "done", "duration": 300.0}
    return client.post(
        f"/admin/modules/{module['id']}/lessons",
        json={"title": title, "kinescope_video_id": video_id},
        headers=headers,
    ).json()


def _upload(client, headers, lesson) -> dict:
    return client.post(f"/admin/lessons/{lesson['id']}/video/upload", json=UPLOAD, headers=headers)


def _video(client, headers, lesson):
    return client.get(f"/admin/lessons/{lesson['id']}/video", headers=headers)


# ---- the client -------------------------------------------------------------------

def test_starting_an_upload_sends_the_key_to_kinescope_only(
    kinescope: KinescopeClient, kinescope_api: FakeKinescope
):
    link = kinescope.create_upload(title="Variables", filename="variables.mp4", filesize=1024)

    request = kinescope_api.requests[0]
    assert str(request.url) == "https://uploader.kinescope.io/v2/init"
    assert request.headers["Authorization"] == "Bearer kinescope-test-key"
    assert json.loads(request.content) == {
        "type": "video",
        "parent_id": "project-1",
        "title": "Variables",
        "filename": "variables.mp4",
        "filesize": 1024,
    }
    assert link.endpoint.startswith("https://")


def test_an_unconfigured_client_refuses_before_calling_out(kinescope_api: FakeKinescope):
    client = KinescopeClient(api_key="", parent_id="project-1", timeout=5)
    client.http = httpx.Client(transport=httpx.MockTransport(kinescope_api.handle))

    with pytest.raises(KinescopeNotConfigured):
        client.create_upload(title="x", filename="x.mp4", filesize=1)
    assert kinescope_api.requests == []


def test_kinescope_errors_carry_their_status(kinescope: KinescopeClient, kinescope_api: FakeKinescope):
    kinescope_api.fail = True

    with pytest.raises(KinescopeError, match="500"):
        kinescope.video_state("vid-1")


def test_a_video_id_cannot_walk_to_another_api_path(
    kinescope: KinescopeClient, kinescope_api: FakeKinescope
):
    kinescope.video_state("../projects")

    assert b"..%2Fprojects" in kinescope_api.requests[0].url.raw_path


def test_deleting_a_video_kinescope_no_longer_has_is_not_an_error(kinescope: KinescopeClient):
    kinescope.delete_video("already-gone")


# ---- uploading and swapping in -------------------------------------------------------

def test_an_admin_starts_an_upload_and_gets_a_tus_endpoint(
    client: TestClient, headers: dict, course: dict, lesson: dict, kinescope_api: FakeKinescope
):
    res = _upload(client, headers, lesson)

    assert res.status_code == 200
    assert res.json()["video_id"] == "vid-1"
    assert res.json()["endpoint"].startswith("https://")
    assert "kinescope-test-key" not in res.text
    init = json.loads(kinescope_api.requests[0].content)
    assert (init["title"], init["filename"], init["filesize"]) == ("Variables", "variables.mp4", 1_048_576)
    tree = client.get(f"/admin/courses/{course['id']}", headers=headers).json()
    view = tree["modules"][0]["lessons"][0]
    assert (view["kinescope_video_id"], view["pending_video_id"]) == (None, "vid-1")


def test_students_see_no_video_while_the_upload_processes(
    client: TestClient, headers: dict, course: dict, lesson: dict, owner: dict
):
    _upload(client, headers, lesson)

    detail = client.get(f"/courses/{course['slug']}/lessons/{lesson['id']}", headers=owner)

    assert detail.json()["video_available"] is False
    assert client.post(f"/video/{lesson['id']}/token", headers=owner).status_code == 409


def test_a_status_check_reports_processing_without_swapping(
    client: TestClient, headers: dict, lesson: dict, kinescope_api: FakeKinescope
):
    _upload(client, headers, lesson)
    kinescope_api.videos["vid-1"]["status"] = "processing"

    assert _video(client, headers, lesson).json() == {
        "video_id": None,
        "pending_video_id": "vid-1",
        "pending_status": "processing",
        "state": "in_progress",
        "duration": None,
    }


def test_a_finished_upload_is_swapped_in_with_its_real_duration(
    client: TestClient, headers: dict, lesson: dict, owner: dict, kinescope_api: FakeKinescope
):
    _upload(client, headers, lesson)
    kinescope_api.videos["vid-1"].update(status="done", duration=421.6)

    assert _video(client, headers, lesson).json() == {
        "video_id": "vid-1",
        "pending_video_id": None,
        "pending_status": "done",
        "state": "complete",
        "duration": 422,
    }
    assert client.post(f"/video/{lesson['id']}/token", headers=owner).json()["video_id"] == "vid-1"


def test_a_replacement_plays_only_once_done_and_then_the_old_video_is_deleted(
    client: TestClient, headers: dict, module: dict, owner: dict, kinescope_api: FakeKinescope
):
    lesson = _lesson_with_video(client, headers, module, kinescope_api, "vid-old")
    _upload(client, headers, lesson)

    assert client.post(f"/video/{lesson['id']}/token", headers=owner).json()["video_id"] == "vid-old"

    kinescope_api.videos["vid-1"]["status"] = "done"
    _video(client, headers, lesson)

    assert client.post(f"/video/{lesson['id']}/token", headers=owner).json()["video_id"] == "vid-1"
    assert "vid-old" not in kinescope_api.videos


def test_an_old_video_another_lesson_still_plays_is_kept(
    client: TestClient, headers: dict, module: dict, kinescope_api: FakeKinescope
):
    first = _lesson_with_video(client, headers, module, kinescope_api, "vid-shared", "Functions")
    _lesson_with_video(client, headers, module, kinescope_api, "vid-shared", "Functions again")
    _upload(client, headers, first)
    kinescope_api.videos["vid-1"]["status"] = "done"

    _video(client, headers, first)

    assert "vid-shared" in kinescope_api.videos
    assert not [r for r in kinescope_api.requests if r.method == "DELETE"]


def test_starting_over_deletes_the_abandoned_upload(
    client: TestClient, headers: dict, lesson: dict, kinescope_api: FakeKinescope
):
    _upload(client, headers, lesson)
    _upload(client, headers, lesson)

    assert _video(client, headers, lesson).json()["pending_video_id"] == "vid-2"
    assert "vid-1" not in kinescope_api.videos


def test_discarding_an_upload_deletes_it(
    client: TestClient, headers: dict, lesson: dict, kinescope_api: FakeKinescope
):
    _upload(client, headers, lesson)

    res = client.delete(f"/admin/lessons/{lesson['id']}/video/pending", headers=headers)

    assert res.status_code == 204
    assert "vid-1" not in kinescope_api.videos
    assert _video(client, headers, lesson).json()["pending_video_id"] is None


def test_discarding_with_nothing_pending_is_404(client: TestClient, headers: dict, lesson: dict):
    res = client.delete(f"/admin/lessons/{lesson['id']}/video/pending", headers=headers)

    assert res.status_code == 404


def test_a_failed_upload_reports_error_and_keeps_the_current_video(
    client: TestClient, headers: dict, module: dict, kinescope_api: FakeKinescope
):
    lesson = _lesson_with_video(client, headers, module, kinescope_api, "vid-old")
    _upload(client, headers, lesson)
    kinescope_api.videos["vid-1"]["status"] = "error"

    body = _video(client, headers, lesson).json()

    assert (body["video_id"], body["pending_video_id"], body["pending_status"], body["state"]) == (
        "vid-old",
        "vid-1",
        "error",
        "failed",
    )


def test_an_upload_kinescope_no_longer_has_reports_missing(
    client: TestClient, headers: dict, lesson: dict, kinescope_api: FakeKinescope
):
    _upload(client, headers, lesson)
    del kinescope_api.videos["vid-1"]

    body = _video(client, headers, lesson).json()

    assert (body["pending_status"], body["state"]) == ("missing", "failed")


@pytest.mark.parametrize(
    "status", ["pending", "uploading", "pre-processing", "processing", "some-new-status"]
)
def test_an_unfinished_upload_is_in_progress(
    client: TestClient, headers: dict, lesson: dict, kinescope_api: FakeKinescope, status: str
):
    _upload(client, headers, lesson)
    kinescope_api.videos["vid-1"]["status"] = status

    assert _video(client, headers, lesson).json()["state"] == "in_progress"


@pytest.mark.parametrize("status", ["error", "aborted", "suspended"])
def test_an_upload_that_cannot_recover_is_failed(
    client: TestClient, headers: dict, lesson: dict, kinescope_api: FakeKinescope, status: str
):
    _upload(client, headers, lesson)
    kinescope_api.videos["vid-1"]["status"] = status

    assert _video(client, headers, lesson).json()["state"] == "failed"


def test_a_linked_video_with_nothing_pending_is_complete(
    client: TestClient, headers: dict, module: dict, kinescope_api: FakeKinescope
):
    lesson = _lesson_with_video(client, headers, module, kinescope_api, "vid-old")

    body = _video(client, headers, lesson).json()

    assert (body["video_id"], body["state"]) == ("vid-old", "complete")
    assert kinescope_api.requests == []


def test_checking_a_lesson_with_nothing_pending_makes_no_kinescope_call(
    client: TestClient, headers: dict, lesson: dict, kinescope_api: FakeKinescope
):
    body = _video(client, headers, lesson).json()

    assert (body["pending_status"], body["state"]) == (None, None)
    assert kinescope_api.requests == []


def test_uploads_without_kinescope_configured_are_a_503(
    client: TestClient, headers: dict, lesson: dict, kinescope: KinescopeClient
):
    kinescope.configured = False

    assert _upload(client, headers, lesson).status_code == 503


def test_kinescope_being_down_is_a_502(
    client: TestClient, headers: dict, lesson: dict, kinescope_api: FakeKinescope
):
    _upload(client, headers, lesson)
    kinescope_api.fail = True

    assert _upload(client, headers, lesson).status_code == 502
    assert _video(client, headers, lesson).status_code == 502


def test_students_cannot_upload(client: TestClient, session: Session, lesson: dict):
    student = _user(session, "student@oner.kg")

    assert _upload(client, _auth(student), lesson).status_code == 403


@pytest.mark.parametrize(
    "body",
    [
        {"filename": "v.mp4", "filesize": 0},
        {"filename": "", "filesize": 10},
        {"filename": "v.mp4"},
    ],
)
def test_an_upload_needs_a_name_and_a_real_size(
    client: TestClient, headers: dict, lesson: dict, body: dict
):
    res = client.post(f"/admin/lessons/{lesson['id']}/video/upload", json=body, headers=headers)

    assert res.status_code == 422


def test_uploading_to_an_unknown_lesson_is_404(client: TestClient, headers: dict):
    assert client.post("/admin/lessons/9999/video/upload", json=UPLOAD, headers=headers).status_code == 404


# ---- deleting content deletes its videos --------------------------------------------

def test_deleting_a_lesson_deletes_its_video_and_its_pending_upload(
    client: TestClient, headers: dict, module: dict, kinescope_api: FakeKinescope
):
    lesson = _lesson_with_video(client, headers, module, kinescope_api, "vid-old")
    _upload(client, headers, lesson)

    res = client.delete(f"/admin/lessons/{lesson['id']}", headers=headers)

    assert res.status_code == 204
    assert kinescope_api.videos == {}


def test_deleting_a_course_keeps_a_video_another_course_still_uses(
    client: TestClient, headers: dict, kinescope_api: FakeKinescope
):
    kinescope_api.videos["vid-shared"] = {"status": "done", "duration": 300.0}
    course_ids = []
    for slug in ("course-a", "course-b"):
        course = client.post("/admin/courses", json={"title": slug, "slug": slug}, headers=headers).json()
        module = client.post(
            f"/admin/courses/{course['id']}/modules", json={"title": "M"}, headers=headers
        ).json()
        client.post(
            f"/admin/modules/{module['id']}/lessons",
            json={"title": "Shared", "kinescope_video_id": "vid-shared"},
            headers=headers,
        )
        course_ids.append(course["id"])

    client.delete(f"/admin/courses/{course_ids[0]}", headers=headers)

    assert "vid-shared" in kinescope_api.videos


def test_a_kinescope_failure_does_not_fail_the_delete(
    client: TestClient, headers: dict, module: dict, kinescope_api: FakeKinescope, caplog
):
    lesson = _lesson_with_video(client, headers, module, kinescope_api, "vid-old")
    kinescope_api.fail = True

    with caplog.at_level(logging.WARNING, logger="oner.video"):
        res = client.delete(f"/admin/lessons/{lesson['id']}", headers=headers)

    assert res.status_code == 204
    assert any("vid-old" in r.getMessage() for r in caplog.records)


# ---- the status webhook ---------------------------------------------------------------

def test_the_webhook_swaps_in_a_finished_upload(
    client: TestClient, headers: dict, lesson: dict, kinescope_api: FakeKinescope, webhook_on
):
    _upload(client, headers, lesson)
    kinescope_api.videos["vid-1"]["status"] = "done"

    res = client.post("/webhooks/kinescope", json=_hook("vid-1"), auth=HOOK_AUTH)

    assert res.status_code == 200
    assert _video(client, headers, lesson).json()["video_id"] == "vid-1"


def test_the_webhook_believes_the_api_not_the_payload(
    client: TestClient, headers: dict, lesson: dict, kinescope_api: FakeKinescope, webhook_on
):
    # Kinescope signs nothing, so a forged "done" must not swap in a video
    # that is still processing.
    _upload(client, headers, lesson)
    kinescope_api.videos["vid-1"]["status"] = "processing"

    client.post("/webhooks/kinescope", json=_hook("vid-1", "done"), auth=HOOK_AUTH)

    body = _video(client, headers, lesson).json()
    assert (body["video_id"], body["pending_video_id"]) == (None, "vid-1")


@pytest.mark.parametrize("auth", [None, ("kinescope", "wrong")])
def test_the_webhook_needs_the_registered_credentials(client: TestClient, webhook_on, auth):
    res = client.post("/webhooks/kinescope", json=_hook("vid-1"), auth=auth)

    assert res.status_code == 401


def test_the_webhook_is_closed_until_credentials_are_configured(client: TestClient):
    res = client.post("/webhooks/kinescope", json=_hook("vid-1"), auth=HOOK_AUTH)

    assert res.status_code == 503


def test_the_webhook_ignores_videos_no_lesson_is_waiting_for(
    client: TestClient, kinescope_api: FakeKinescope, webhook_on
):
    res = client.post("/webhooks/kinescope", json=_hook("vid-unknown"), auth=HOOK_AUTH)

    assert res.status_code == 200
    assert kinescope_api.requests == []


def test_the_webhook_ignores_other_events(
    client: TestClient, headers: dict, lesson: dict, kinescope_api: FakeKinescope, webhook_on
):
    _upload(client, headers, lesson)
    kinescope_api.requests.clear()

    res = client.post("/webhooks/kinescope", json=_hook("vid-1", event="live.created"), auth=HOOK_AUTH)

    assert res.status_code == 200
    assert kinescope_api.requests == []


def test_the_webhook_asks_for_a_retry_when_kinescope_is_down(
    client: TestClient, headers: dict, lesson: dict, kinescope_api: FakeKinescope, webhook_on
):
    _upload(client, headers, lesson)
    kinescope_api.fail = True

    res = client.post("/webhooks/kinescope", json=_hook("vid-1"), auth=HOOK_AUTH)

    assert res.status_code == 502


# ---- odd answers from Kinescope ---------------------------------------------------------

def _client_answering(response: httpx.Response) -> KinescopeClient:
    client = KinescopeClient(api_key="kinescope-test-key", parent_id="project-1", timeout=5)
    client.http = httpx.Client(transport=httpx.MockTransport(lambda request: response))
    return client


def test_an_upload_link_without_an_endpoint_is_an_error():
    client = _client_answering(httpx.Response(200, json={"data": {"id": "vid-1"}}))

    with pytest.raises(KinescopeError, match="no video id or endpoint"):
        client.create_upload(title="x", filename="x.mp4", filesize=1)


def test_an_html_error_page_is_still_a_clean_error():
    # A proxy in front of Kinescope answers with HTML, not their JSON envelope.
    client = _client_answering(httpx.Response(502, text="<html>Bad Gateway</html>"))

    with pytest.raises(KinescopeError, match="502"):
        client.video_state("vid-1")


def test_a_success_without_the_data_envelope_is_an_error():
    client = _client_answering(httpx.Response(200, json={"unexpected": True}))

    with pytest.raises(KinescopeError, match="unusable"):
        client.video_state("vid-1")


def test_deleting_videos_without_kinescope_configured_makes_no_call(
    kinescope: KinescopeClient, kinescope_api: FakeKinescope
):
    kinescope.configured = False

    delete_videos(kinescope, ["vid-1"])

    assert kinescope_api.requests == []
