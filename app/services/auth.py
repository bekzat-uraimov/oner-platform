"""Auth business logic: creating accounts and verifying credentials.

Routes stay thin; the rules about uniqueness and password checking live here and
are unit-testable without HTTP.
"""

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.security import hash_password, verify_password
from app.models import User


class EmailAlreadyRegistered(Exception):
    """Raised when registering an email that already exists."""


def normalize_email(email: str) -> str:
    # Phone keyboards capitalise the first letter. Stored as typed, Aigul@mail.ru
    # couldn't log in as aigul@mail.ru, and could register a second account.
    return email.strip().lower()


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.exec(select(User).where(User.email == normalize_email(email))).first()


def register_user(session: Session, email: str, password: str) -> User:
    email = normalize_email(email)
    if get_user_by_email(session, email) is not None:
        raise EmailAlreadyRegistered(email)

    user = User(email=email, password_hash=hash_password(password))
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        # Two sign-ups with one email at the same moment: both passed the check
        # above, and the unique index stops the second.
        session.rollback()
        raise EmailAlreadyRegistered(email)
    session.refresh(user)
    return user


def authenticate(session: Session, email: str, password: str) -> User | None:
    """Return the user iff email exists and password matches, else None."""
    user = get_user_by_email(session, email)
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
