"""A clean start leaves the database at head, with nobody running Alembic.

This is the promise of roadmap 11.1: `docker compose up` and nothing else. The
test runs the real entrypoint script against a brand new database and checks
where it left it, so the promise is verified rather than assumed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
import yaml
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
ENTRYPOINT = REPO_ROOT / "infra" / "docker" / "entrypoint.sh"
DOCKERFILE = REPO_ROOT / "infra" / "docker" / "backend.Dockerfile"
COMPOSE_FILE = REPO_ROOT / "infra" / "docker-compose.yml"

STARTUP_DATABASE = "vokara_startup_test"


@pytest.fixture
def clean_database_url(database_url: str) -> Iterator[str]:
    """A database created for this test and dropped afterwards."""
    admin = create_engine(database_url, future=True, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{STARTUP_DATABASE}" WITH (FORCE)'))
        connection.execute(text(f'CREATE DATABASE "{STARTUP_DATABASE}"'))

    parts = urlsplit(database_url)
    try:
        yield urlunsplit(parts._replace(path=f"/{STARTUP_DATABASE}"))
    finally:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{STARTUP_DATABASE}" WITH (FORCE)'))
        admin.dispose()


def test_entrypoint_brings_a_fresh_database_to_head(clean_database_url: str) -> None:
    environment = {
        **os.environ,
        "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}",
        "VOKARA_APP_DIR": str(BACKEND_ROOT),
        "DATABASE_URL": clean_database_url,
        "VOKARA_MIGRATION_ATTEMPTS": "1",
    }

    # `true` stands in for uvicorn: what is under test is what happens before it.
    result = subprocess.run(  # noqa: S603
        ["/bin/sh", str(ENTRYPOINT), "/bin/true"],
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, result.stderr

    engine = create_engine(clean_database_url, future=True)
    with engine.connect() as connection:
        revision = connection.execute(text("select version_num from alembic_version")).scalar_one()
        tables = connection.execute(
            text("select count(*) from pg_tables where schemaname = 'public'")
        ).scalar_one()
        seeded = connection.execute(text("select count(*) from candidates")).scalar_one()
        extension = connection.execute(
            text("select count(*) from pg_extension where extname = 'vector'")
        ).scalar_one()
    engine.dispose()

    assert revision == "0001"
    assert tables == 10  # nine tables plus alembic_version
    assert seeded == 1
    assert extension == 1


def test_the_worker_does_not_migrate(clean_database_url: str) -> None:
    """Two processes applying the same migration is a race with no prize."""
    environment = {
        **os.environ,
        "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}",
        "VOKARA_APP_DIR": str(BACKEND_ROOT),
        "DATABASE_URL": clean_database_url,
        "VOKARA_APPLY_MIGRATIONS": "0",
    }

    result = subprocess.run(  # noqa: S603
        ["/bin/sh", str(ENTRYPOINT), "/bin/true"],
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr

    engine = create_engine(clean_database_url, future=True)
    with engine.connect() as connection:
        tables = connection.execute(
            text("select count(*) from pg_tables where schemaname = 'public'")
        ).scalar_one()
    engine.dispose()

    assert tables == 0


def test_the_entrypoint_is_wired_in_the_image_and_in_the_compose() -> None:
    """A script nobody runs migrates nothing."""
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    assert 'ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]' in dockerfile

    services = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))["services"]
    assert services["api"]["entrypoint"] == ["/usr/local/bin/entrypoint.sh"]
    assert services["worker"]["environment"]["VOKARA_APPLY_MIGRATIONS"] == "0"
