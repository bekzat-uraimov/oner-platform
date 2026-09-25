"""Database engine + session wiring.

A single engine per process; `get_session` is the FastAPI dependency that hands a
short-lived Session to a request and closes it afterward.
"""

from collections.abc import Generator

from sqlmodel import Session, create_engine

from app.core.config import get_settings

settings = get_settings()

# `echo=debug` mirrors SQL to logs only in dev. pool_pre_ping survives dropped
# connections on managed Postgres.
engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
