"""Day 2: the schema exists, relationships wire up, and the integrity rules hold."""

from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models import (
    Course,
    CourseStatus,
    Currency,
    Entitlement,
    Gateway,
    Lesson,
    Material,
    MaterialType,
    Module,
    Purchase,
    PurchaseStatus,
    User,
    UserRole,
)


def _published_course(session: Session) -> Course:
    course = Course(
        title="Test Course",
        slug="test-course",
        price=Decimal("1000.00"),
        currency=Currency.KGS,
        status=CourseStatus.published,
    )
    session.add(course)
    session.commit()
    session.refresh(course)
    return course


def test_user_defaults(session: Session) -> None:
    user = User(email="a@example.com", password_hash="x")
    session.add(user)
    session.commit()
    session.refresh(user)
    assert user.id is not None
    assert user.role is UserRole.student  # default
    assert user.created_at is not None


def test_user_email_unique(session: Session) -> None:
    session.add(User(email="dup@example.com", password_hash="x"))
    session.commit()
    session.add(User(email="dup@example.com", password_hash="y"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_course_module_lesson_tree(session: Session) -> None:
    course = Course(title="C", slug="c", status=CourseStatus.draft)
    module = Module(title="M1", order=0)
    module.lessons.append(Lesson(title="L1", order=0, duration=120))
    module.lessons.append(Lesson(title="L2", order=1))
    course.modules.append(module)
    session.add(course)
    session.commit()
    session.refresh(course)

    assert len(course.modules) == 1
    assert len(course.modules[0].lessons) == 2
    # back-reference resolves
    assert course.modules[0].lessons[0].module.title == "M1"


def test_entitlement_grants_access_and_is_unique(session: Session) -> None:
    user = User(email="owner@example.com", password_hash="x")
    course = _published_course(session)
    session.add(user)
    session.commit()
    session.refresh(user)

    session.add(Entitlement(user_id=user.id, course_id=course.id))
    session.commit()

    owned = session.exec(
        select(Entitlement).where(
            Entitlement.user_id == user.id, Entitlement.course_id == course.id
        )
    ).first()
    assert owned is not None

    # Owning the same course twice must be impossible (stops double-grants).
    session.add(Entitlement(user_id=user.id, course_id=course.id))
    with pytest.raises(IntegrityError):
        session.commit()


def test_purchase_links_to_entitlement(session: Session) -> None:
    user = User(email="buyer@example.com", password_hash="x")
    course = _published_course(session)
    session.add(user)
    session.commit()
    session.refresh(user)

    purchase = Purchase(
        user_id=user.id,
        course_id=course.id,
        gateway=Gateway.freedompay,
        gateway_txn_id="txn-123",
        amount=Decimal("1000.00"),
        currency=Currency.KGS,
        status=PurchaseStatus.paid,
    )
    session.add(purchase)
    session.commit()
    session.refresh(purchase)

    ent = Entitlement(
        user_id=user.id, course_id=course.id, source_purchase_id=purchase.id
    )
    session.add(ent)
    session.commit()
    session.refresh(ent)

    assert ent.source_purchase.gateway_txn_id == "txn-123"
    assert purchase.entitlement.id == ent.id


def test_gateway_txn_id_unique(session: Session) -> None:
    user = User(email="u@example.com", password_hash="x")
    course = _published_course(session)
    session.add(user)
    session.commit()
    session.refresh(user)

    session.add(
        Purchase(user_id=user.id, course_id=course.id, gateway_txn_id="dupe")
    )
    session.commit()
    session.add(
        Purchase(user_id=user.id, course_id=course.id, gateway_txn_id="dupe")
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_material_attaches_to_lesson_or_course(session: Session) -> None:
    course = _published_course(session)
    module = Module(title="M", order=0, course_id=course.id)
    session.add(module)
    session.commit()
    session.refresh(module)
    lesson = Lesson(title="L", order=0, module_id=module.id)
    session.add(lesson)
    session.commit()
    session.refresh(lesson)

    course_mat = Material(
        course_id=course.id, title="Syllabus", storage_key="k/syllabus.pdf", type=MaterialType.pdf
    )
    lesson_mat = Material(
        lesson_id=lesson.id, title="Slides", storage_key="k/slides.pdf", type=MaterialType.pdf
    )
    session.add(course_mat)
    session.add(lesson_mat)
    session.commit()
    session.refresh(course_mat)
    session.refresh(lesson_mat)

    assert course_mat.course.id == course.id
    assert course_mat.lesson is None
    assert lesson_mat.lesson.id == lesson.id
    assert lesson_mat.course is None
