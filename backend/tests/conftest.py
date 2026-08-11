"""Shared fixtures: real Postgres and real Redis (art. VI).

Integration tests run against the same images the user runs. An embedded
Postgres would not carry pgvector reliably, and the point of these tests is
what the database enforces — CHECKs, partial unique indexes, the immutability
trigger — none of which a fake reproduces.

Containers are session scoped and only start when a test asks for them.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from app.core.config import get_settings

BACKEND_ROOT = Path(__file__).resolve().parents[1]
# Same image and major version as infra/docker-compose.yml.
POSTGRES_IMAGE = "pgvector/pgvector:pg16"
REDIS_IMAGE = "redis:7.4-alpine"


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    with PostgresContainer(
        POSTGRES_IMAGE,
        username="vokara",
        password="vokara_test",
        dbname="vokara_test",
        driver="psycopg",
    ) as container:
        yield container


@pytest.fixture(scope="session")
def database_url(postgres_container: PostgresContainer) -> str:
    return str(postgres_container.get_connection_url())


@pytest.fixture(scope="session")
def redis_container() -> Iterator[RedisContainer]:
    with RedisContainer(REDIS_IMAGE) as container:
        yield container


@pytest.fixture(scope="session")
def redis_url(redis_container: RedisContainer) -> str:
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    return f"redis://{host}:{port}/0"


def alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "app" / "db" / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture(scope="session")
def migrated_database(database_url: str) -> str:
    """Bring the schema to head once per session, the way startup does."""
    # Anything that reads Settings from here on must see the throwaway
    # database, not whatever the developer has in their .env.
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()
    command.upgrade(alembic_config(database_url), "head")
    return database_url


@pytest.fixture(scope="session")
def db_engine(migrated_database: str) -> Iterator[Engine]:
    engine = create_engine(migrated_database, future=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    """A session inside a transaction that is always rolled back.

    Every test sees the migrated schema and leaves nothing behind, so order
    between tests cannot matter.
    """
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        expire_on_commit=False,
        # A commit inside the code under test lands on a savepoint, so the
        # outer rollback still wipes everything.
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
