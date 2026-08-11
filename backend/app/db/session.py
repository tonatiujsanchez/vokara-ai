"""Engine and session factory.

Synchronous on purpose (art. VII). The long call is the LLM one and it runs in
the Celery worker, not in the request; FastAPI runs `def` endpoints in a
thread pool, so a blocking query never occupies the event loop. One engine
serves the API, the worker, the migrations and the tests.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

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


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """One engine per process, built on first use.

    Lazily rather than at import time so configuration read later — a test
    pointing at a throwaway container, for instance — is not too late.
    """
    return create_db_engine()


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, roll back on failure."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
