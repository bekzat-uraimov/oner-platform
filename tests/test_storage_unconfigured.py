"""A deployment without R2 credentials must still answer: storage routes say 503,
and deleting content works, leaving nothing to clean up in a bucket that isn't there.
"""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.security import create_access_token, hash_password
from app.models import Course, CourseStatus, Currency, User, UserRole
from app.services.storage import R2Client, get_storage


def _blank_storage() -> R2Client:
    return R2Client(account_id="", bucket="", access_key_id="", secret_access_key="", url_ttl_s=60)


def _admin_headers(session: Session) -> dict:
    admin = User(email="admin@oner.kg", password_hash=hash_password("supersecret123"), role=UserRole.admin)
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return {"Authorization": f"Bearer {create_access_token(admin.id)}"}


def test_an_unconfigured_client_builds_and_says_so():
    storage = _blank_storage()

    assert storage.configured is False


def test_default_settings_give_a_usable_storage_dependency():
    get_storage.cache_clear()
    try:
        assert get_storage().configured is False
    finally:
        get_storage.cache_clear()


def test_without_r2_deleting_a_course_still_works(client: TestClient, session: Session):
    client.app.dependency_overrides[get_storage] = _blank_storage
    headers = _admin_headers(session)
    course = Course(title="Draft", slug="draft", price=Decimal("0"), currency=Currency.KGS, status=CourseStatus.draft)
    session.add(course)
    session.commit()
    session.refresh(course)

    assert client.delete(f"/admin/courses/{course.id}", headers=headers).status_code == 204


def test_without_r2_upload_links_are_a_503_not_a_500(client: TestClient, session: Session):
    client.app.dependency_overrides[get_storage] = _blank_storage
    headers = _admin_headers(session)

    res = client.post("/admin/materials/upload-url", json={"filename": "notes.pdf"}, headers=headers)

    assert res.status_code == 503
