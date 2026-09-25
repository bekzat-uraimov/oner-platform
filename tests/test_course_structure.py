"""The course page: what a buyer reads before paying, and what an owner finds
inside each lesson.

    COURSE   description, what you'll learn, requirements, course-wide materials
      MODULE   description
        LESSON   description, video, materials
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.security import create_access_token, hash_password
from app.models import User, UserRole
from app.services.entitlements import grant
from app.services.storage import new_storage_key

TREE = {
    "Python Foundations": ["Variables", "Functions", "Classes"],
    "FastAPI": ["Routes", "Validation", "Dependencies"],
    "PostgreSQL": ["Tables", "Queries"],
}


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


def _build_course(client: TestClient, headers: dict) -> dict:
    """The Python Backend course from the brief, built through the admin API."""
    course = client.post(
        "/admin/courses",
        json={
            "title": "Python Backend Development",
            "slug": "python-backend",
            "description": "From plain Python to FastAPI on PostgreSQL.",
            "learning_outcomes": "Write idiomatic Python\nBuild a FastAPI service",
            "requirements": "Python 3.12 installed",
            "price": "6990.00",
            "status": "published",
        },
        headers=headers,
    ).json()
    for module_title, lesson_titles in TREE.items():
        module = client.post(
            f"/admin/courses/{course['id']}/modules",
            json={"title": module_title, "description": f"About {module_title}"},
            headers=headers,
        ).json()
        for lesson_title in lesson_titles:
            lesson = client.post(
                f"/admin/modules/{module['id']}/lessons",
                json={
                    "title": lesson_title,
                    "description": f"{lesson_title} explained",
                    "kinescope_video_id": f"kine-{lesson_title.lower()}",
                },
                headers=headers,
            ).json()
            client.post(
                "/admin/materials",
                json={
                    "title": f"{lesson_title} notes",
                    "storage_key": new_storage_key("notes.pdf"),
                    "lesson_id": lesson["id"],
                },
                headers=headers,
            )
    client.post(
        "/admin/materials",
        json={
            "title": "Syllabus",
            "storage_key": new_storage_key("syllabus.pdf"),
            "course_id": course["id"],
        },
        headers=headers,
    )
    return course


def test_the_public_course_page_has_the_whole_tree(client: TestClient, headers: dict):
    _build_course(client, headers)

    page = client.get("/courses/python-backend").json()

    assert page["learning_outcomes"] == "Write idiomatic Python\nBuild a FastAPI service"
    assert page["requirements"] == "Python 3.12 installed"
    assert [m["title"] for m in page["materials"]] == ["Syllabus"]
    assert [
        (module["title"], module["description"], [lesson["title"] for lesson in module["lessons"]])
        for module in page["modules"]
    ] == [
        ("Python Foundations", "About Python Foundations", ["Variables", "Functions", "Classes"]),
        ("FastAPI", "About FastAPI", ["Routes", "Validation", "Dependencies"]),
        ("PostgreSQL", "About PostgreSQL", ["Tables", "Queries"]),
    ]
    variables = page["modules"][0]["lessons"][0]
    assert variables["description"] == "Variables explained"
    assert [m["title"] for m in variables["materials"]] == ["Variables notes"]


def test_the_public_page_never_shows_where_files_live_or_which_video(
    client: TestClient, headers: dict
):
    _build_course(client, headers)

    page = client.get("/courses/python-backend")

    assert "storage_key" not in page.text
    assert "materials/" not in page.text
    assert "kine-" not in page.text


def test_the_catalog_list_stays_light(client: TestClient, headers: dict):
    # Long text and the tree belong on the course page, not in every list item.
    _build_course(client, headers)

    item = client.get("/courses").json()[0]

    assert "learning_outcomes" not in item
    assert "modules" not in item


def test_an_owner_reads_a_lesson_with_its_description_and_materials(
    client: TestClient, session: Session, headers: dict
):
    course = _build_course(client, headers)
    buyer = _user(session, "buyer@oner.kg")
    grant(session, buyer.id, course["id"])
    routes = client.get("/courses/python-backend").json()["modules"][1]["lessons"][0]

    res = client.get(f"/courses/python-backend/lessons/{routes['id']}", headers=_auth(buyer))

    assert res.status_code == 200
    body = res.json()
    assert body["description"] == "Routes explained"
    assert body["video_available"] is True
    assert [m["title"] for m in body["materials"]] == ["Routes notes"]


def test_a_listed_material_id_is_what_an_owner_downloads(
    client: TestClient, session: Session, headers: dict
):
    # The gap this closes: download worked, but no response ever told a buyer
    # which id to ask for.
    course = _build_course(client, headers)
    buyer = _user(session, "buyer2@oner.kg")
    grant(session, buyer.id, course["id"])
    syllabus = client.get("/courses/python-backend").json()["materials"][0]

    res = client.get(f"/materials/{syllabus['id']}/download", headers=_auth(buyer))

    assert res.status_code == 200
    assert res.json()["filename"] == "Syllabus.pdf"


def test_a_non_owner_sees_material_titles_but_cannot_download(
    client: TestClient, session: Session, headers: dict
):
    _build_course(client, headers)
    stranger = _user(session, "stranger@oner.kg")
    syllabus = client.get("/courses/python-backend").json()["materials"][0]

    res = client.get(f"/materials/{syllabus['id']}/download", headers=_auth(stranger))

    assert res.status_code == 403


def test_materials_are_listed_in_the_order_they_were_added(client: TestClient, headers: dict):
    course = client.post(
        "/admin/courses", json={"title": "T", "slug": "t", "status": "published"}, headers=headers
    ).json()
    for title in ("Cheat sheet", "Answers", "Bonus"):
        client.post(
            "/admin/materials",
            json={"title": title, "storage_key": new_storage_key("x.pdf"), "course_id": course["id"]},
            headers=headers,
        )

    page = client.get("/courses/t").json()

    assert [m["title"] for m in page["materials"]] == ["Cheat sheet", "Answers", "Bonus"]


def test_descriptions_can_be_edited_and_cleared(client: TestClient, headers: dict):
    course = client.post(
        "/admin/courses", json={"title": "T", "slug": "t"}, headers=headers
    ).json()
    module = client.post(
        f"/admin/courses/{course['id']}/modules", json={"title": "Day 1"}, headers=headers
    ).json()
    lesson = client.post(
        f"/admin/modules/{module['id']}/lessons", json={"title": "L1"}, headers=headers
    ).json()

    client.patch(
        f"/admin/courses/{course['id']}",
        json={"learning_outcomes": "Outcomes", "requirements": "Needs"},
        headers=headers,
    )
    client.patch(f"/admin/modules/{module['id']}", json={"description": "Module text"}, headers=headers)
    client.patch(f"/admin/lessons/{lesson['id']}", json={"description": "Lesson text"}, headers=headers)
    view = client.get(f"/admin/courses/{course['id']}", headers=headers).json()

    assert (view["learning_outcomes"], view["requirements"]) == ("Outcomes", "Needs")
    assert view["modules"][0]["description"] == "Module text"
    assert view["modules"][0]["lessons"][0]["description"] == "Lesson text"

    client.patch(f"/admin/modules/{module['id']}", json={"description": None}, headers=headers)
    view = client.get(f"/admin/courses/{course['id']}", headers=headers).json()

    assert view["modules"][0]["description"] is None


def test_the_new_text_fields_are_optional(client: TestClient, headers: dict):
    course = client.post("/admin/courses", json={"title": "T", "slug": "t"}, headers=headers)
    module = client.post(
        f"/admin/courses/{course.json()['id']}/modules", json={"title": "Day 1"}, headers=headers
    )
    lesson = client.post(
        f"/admin/modules/{module.json()['id']}/lessons", json={"title": "L1"}, headers=headers
    )

    assert (course.status_code, module.status_code, lesson.status_code) == (201, 201, 201)
    assert course.json()["learning_outcomes"] is None
    assert module.json()["description"] is None
    assert lesson.json()["description"] is None
