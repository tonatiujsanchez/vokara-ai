"""One .env, in the repository root, and no way to grow a second one.

Compose takes the directory of the file passed with -f as its project
directory, so it would look for its own .env inside infra/. Two rules keep that
from happening, and this test is what keeps them true (quickstart §0):

1. `api` and `worker` read `../.env`, with required: false so a fresh clone
   without one still boots.
2. No `${...}` interpolation anywhere. It is the only construction that would
   read the project-directory .env and quietly reintroduce a second location
   for the same key.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

INFRA = Path(__file__).resolve().parents[3] / "infra"
COMPOSE_FILE = INFRA / "docker-compose.yml"
OVERRIDE_FILE = INFRA / "docker-compose.override.yml"
SERVICES_READING_ENV_FILE = ("api", "worker")


def _existing_compose_files() -> list[Path]:
    return [path for path in (COMPOSE_FILE, OVERRIDE_FILE) if path.is_file()]


def _services(compose: Path) -> dict[str, Any]:
    document: dict[str, Any] = yaml.safe_load(compose.read_text(encoding="utf-8")) or {}
    services: dict[str, Any] = document.get("services") or {}
    return services


def test_compose_file_exists() -> None:
    assert COMPOSE_FILE.is_file()


@pytest.mark.parametrize("compose", _existing_compose_files(), ids=lambda path: path.name)
def test_no_interpolation_anywhere(compose: Path) -> None:
    lines = [
        f"{number}: {line.strip()}"
        for number, line in enumerate(compose.read_text(encoding="utf-8").splitlines(), start=1)
        if "${" in line
    ]
    assert not lines, (
        f"{compose.name} usa interpolación, que leería un .env de infra/:\n" + "\n".join(lines)
    )


@pytest.mark.parametrize("service", SERVICES_READING_ENV_FILE)
def test_services_read_the_root_env_file_and_survive_without_it(service: str) -> None:
    definition = _services(COMPOSE_FILE)[service]
    entries = definition.get("env_file")

    assert entries, f"{service} no declara env_file"
    assert [entry.get("path") for entry in entries] == ["../.env"], (
        f"{service} debe leer el .env de la raíz del repositorio, y solo ese"
    )
    assert all(entry.get("required") is False for entry in entries), (
        f"{service} exige que exista el .env: un clon virgen no arrancaría"
    )


def test_the_env_file_of_the_root_is_the_only_one() -> None:
    assert not (INFRA / ".env").exists(), "No debe existir infra/.env (quickstart §0)"
    assert not (INFRA / ".env.example").exists(), "No debe existir infra/.env.example"


def test_compose_has_exactly_the_four_services() -> None:
    """Four services and not one more (art. VII). No beat (research R-28)."""
    assert sorted(_services(COMPOSE_FILE)) == ["api", "postgres", "redis", "worker"]


def test_postgres_and_redis_are_not_published_at_all() -> None:
    services = _services(COMPOSE_FILE)
    for name in ("postgres", "redis"):
        assert not services[name].get("ports"), f"{name} no se publica al host (ADR-008)"
