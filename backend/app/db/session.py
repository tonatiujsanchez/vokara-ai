"""Engine and session factory.

Synchronous on purpose (art. VII). The long call is the LLM one and it runs in
the Celery worker, not in the request; FastAPI runs `def` endpoints in a
thread pool, so a blocking query never occupies the event loop. One engine
serves the API, the worker, the migrations and the tests.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def create_db_engine(url: str | None = None) -> Engine:
    settings = get_settings()
    return create_engine(
        url or settings.database_url,
        # A local installation sits idle for hours; a stale connection must not
        # surface as an error on the next click.
        pool_pre_ping=True,
        future=True,
    )


engine: Engine = create_db_engine()
SessionFactory: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, roll back on failure."""
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
