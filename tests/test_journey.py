"""The whole product in one test: register → browse → buy → own → watch.

Every other test file checks one day's work in isolation. This one fails if any
day regresses, and it's the only test that walks the path a real customer does.
"""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import (
    Course,
    CourseStatus,
    Currency,
    Lesson,
    Material,
    MaterialType,
    Module,
)
from app.services.freedompay import make_sig
from tests.conftest import TEST_SECRET

EMAIL = "student@oner.kg"
PASSWORD = "supersecret123"
VIDEO_ID = "kine-journey-1"


def _seed_course(session: Session) -> tuple[Course, Lesson]:
    course = Course(
        title="Python Basics",
        slug="python-basics",
        price=Decimal("2500.00"),
        currency=Currency.KGS,
        status=CourseStatus.published,
    )
    module = Module(title="Getting started", order=0)
    module.lessons.append(
        Lesson(title="Variables", order=0, duration=420, kinescope_video_id=VIDEO_ID)
    )
    course.modules.append(module)
    session.add(course)
    session.commit()
    session.refresh(course)
    lesson = session.exec(select(Lesson)).one()
    session.add(
        Material(
            course_id=course.id,
            title="Workbook",
            storage_key="materials/workbook.pdf",
            type=MaterialType.pdf,
        )
    )
    session.commit()
    return course, lesson


def _signed_callback(purchase_id: int, amount: str, currency: str) -> dict[str, str]:
    params = {
        "pg_order_id": str(purchase_id),
        "pg_payment_id": "pg-journey-1",
        "pg_amount": amount,
        "pg_currency": currency,
        "pg_result": "1",
        "pg_salt": "journeysalt",
        "pg_testing_mode": "1",
    }
    params["pg_sig"] = make_sig("result", params, TEST_SECRET)
    return params


def test_a_student_registers_buys_and_watches(client: TestClient, session: Session):
    course, lesson = _seed_course(session)
    material = session.exec(select(Material)).one()

    # 1. Register and log in.
    assert client.post(
        "/auth/register", json={"email": EMAIL, "password": PASSWORD}
    ).status_code == 201
    token = client.post(
        "/auth/login", data={"username": EMAIL, "password": PASSWORD}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Browse. The catalog shows the course but never the playable video id.
    listing = client.get("/courses").json()
    assert [c["slug"] for c in listing] == ["python-basics"]
    detail = client.get(f"/courses/{course.slug}")
    assert VIDEO_ID not in detail.text

    # 3. Nothing is owned, and playback is refused.
    assert client.get("/me/courses", headers=headers).json() == []
    assert client.post(f"/video/{lesson.id}/token", headers=headers).status_code == 403
    assert (
        client.get(f"/materials/{material.id}/download", headers=headers).status_code
        == 403
    )

    # 4. Start checkout. Still owns nothing — a payment link is not a purchase.
    checkout = client.post(
        "/checkout", json={"course_id": course.id}, headers=headers
    ).json()
    assert checkout["redirect_url"]
    assert client.get("/me/courses", headers=headers).json() == []

    # 5. FreedomPay confirms the payment server-to-server.
    callback = client.post(
        "/webhooks/freedompay/result",
        data=_signed_callback(
            checkout["purchase_id"], checkout["amount"], checkout["currency"]
        ),
    )
    assert callback.status_code == 200

    # 6. Now it's owned.
    owned = client.get("/me/courses", headers=headers).json()
    assert [c["slug"] for c in owned] == ["python-basics"]

    # 7. The video id is finally released, with a token for it.
    video = client.post(f"/video/{lesson.id}/token", headers=headers)
    assert video.status_code == 200
    assert video.json()["video_id"] == VIDEO_ID

    # 8. Kinescope asks whether to release the key, and we say yes.
    play = client.post(
        "/drm/auth",
        json={
            "id": VIDEO_ID,
            "token": video.json()["drm_auth_token"],
            "type": "video",
            "ip": "11.22.33.0",
            "user_agent": "Mozilla/5.0",
        },
    )
    assert play.status_code == 200

    # 9. And the workbook comes down on a link that expires in a minute.
    download = client.get(f"/materials/{material.id}/download", headers=headers)
    assert download.status_code == 200
    assert download.json()["filename"] == "Workbook.pdf"
    assert download.json()["expires_in"] == 60
