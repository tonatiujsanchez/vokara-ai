"""GET /api/v1/health against a real database.

This is the endpoint of checkpoint A: it reads the applied revision from
alembic_version, so a green answer proves the whole path — container, engine,
migration, router — and not just that the process is up.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_engine, get_session_factory
from app.main import app


@pytest.fixture
def client(migrated_database: str) -> Iterator[TestClient]:
    # The fixture already pointed the configuration at the throwaway database;
    # drop the cached engine so this client uses it.
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    get_engine.cache_clear()
    get_session_factory.cache_clear()


def test_health_reports_the_revision_read_from_the_database(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "migration_revision": "0001",
    }


def test_every_response_carries_its_request_id(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.headers["X-Request-ID"]


def test_a_supplied_request_id_is_honoured(client: TestClient) -> None:
    """Following one action across API and worker logs needs a stable id."""
    response = client.get("/api/v1/health", headers={"X-Request-ID": "abc-123"})

    assert response.headers["X-Request-ID"] == "abc-123"


def test_health_degrades_instead_of_leaking_when_the_database_is_gone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No connection string, no stack trace, no host name in the answer (art. V)."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://nobody:nothing@127.0.0.1:1/none")
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    from app.core.config import get_settings

    get_settings.cache_clear()

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/health")
    finally:
        get_settings.cache_clear()
        get_engine.cache_clear()
        get_session_factory.cache_clear()

    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "degraded", "database": "unavailable", "migration_revision": None}
    assert "nobody" not in response.text
    assert "127.0.0.1" not in response.text
