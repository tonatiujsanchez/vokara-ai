"""Interrupting the wizard and coming back (SC-015, US1 AC12, FR-014).

The scenario is the ordinary one: someone acknowledges the disclosure,
configures generation, closes the browser and returns later. What must not
happen is being asked again for the acknowledgement or for a key that was
already verified — that is the difference between persisting the *facts* of the
first run and persisting a step counter (research R-18).

A new client stands in for the reopening: the state travels in the database and
in local configuration, not in a session, which is the property being checked.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.db.session import get_engine, get_session_factory
from app.domain.capability import Capability
from app.domain.disclosure import CURRENT_DISCLOSURE
from app.main import app
from tests.integration.conftest import A_VALID_KEY, ProbeDirector

BASE = "/api/v1/setup"


@pytest.fixture
def reopen(migrated_database: str, data_dir: Path, db_engine: Engine) -> Iterator[TestClient]:
    """A second client over the same database and the same data directory."""
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    with TestClient(app) as client:
        yield client


def acknowledge(client: TestClient) -> None:
    client.post(
        f"{BASE}/disclosure-acknowledgement",
        json={"disclosure_version": CURRENT_DISCLOSURE.version, "acknowledged": True},
    )


def test_with_only_generation_verified_the_wizard_resumes_at_providers(
    setup_client: TestClient, probes: ProbeDirector, offerable_provider: str, reopen: TestClient
) -> None:
    """US1 AC12: it resumes at embeddings, not at the beginning."""
    acknowledge(setup_client)
    setup_client.put(
        f"{BASE}/providers/generation",
        json={"provider": offerable_provider, "api_key": A_VALID_KEY},
    )

    state = reopen.get(f"{BASE}/state").json()

    assert state["pending_step"] == "providers"
    assert state["providers"]["generation"]["is_usable"] is True
    assert state["providers"]["embeddings"] is None


def test_the_acknowledgement_is_never_asked_for_twice(
    setup_client: TestClient, probes: ProbeDirector, offerable_provider: str, reopen: TestClient
) -> None:
    """FR-014: what was accepted stays accepted across restarts."""
    acknowledge(setup_client)

    disclosure = reopen.get(f"{BASE}/disclosure").json()

    assert disclosure["acknowledged"] is True
    assert disclosure["acknowledged_version"] == CURRENT_DISCLOSURE.version
    assert disclosure["acknowledged_at"] is not None
    assert reopen.get(f"{BASE}/state").json()["disclosure_acknowledged"] is True


def test_a_verified_key_is_never_asked_for_again(
    setup_client: TestClient, probes: ProbeDirector, offerable_provider: str, reopen: TestClient
) -> None:
    """The credential lives in local configuration and survives the restart."""
    acknowledge(setup_client)
    setup_client.put(
        f"{BASE}/providers/generation",
        json={"provider": offerable_provider, "api_key": A_VALID_KEY},
    )

    generation = reopen.get(f"{BASE}/providers/generation").json()

    assert generation["credential_status"] == "configured"
    assert generation["preflight"]["result"] == "verified"
    assert A_VALID_KEY not in reopen.get(f"{BASE}/providers/generation").text


def test_reopening_after_the_email_step_shows_nothing_pending(
    setup_client: TestClient, probes: ProbeDirector, offerable_provider: str, reopen: TestClient
) -> None:
    """FR-015: once concluded, the first run never shows up again."""
    acknowledge(setup_client)
    for capability in Capability:
        setup_client.put(
            f"{BASE}/providers/{capability.value}",
            json={"provider": offerable_provider, "api_key": A_VALID_KEY},
        )
    setup_client.post(f"{BASE}/email/skip")

    state = reopen.get(f"{BASE}/state").json()

    assert state["pending_step"] is None
    assert state["is_complete"] is True


def test_each_step_moves_the_pending_one_exactly_once(
    setup_client: TestClient, probes: ProbeDirector, offerable_provider: str
) -> None:
    """The whole walk, in order, as the SPA would drive it."""
    assert setup_client.get(f"{BASE}/state").json()["pending_step"] == "disclosure"

    acknowledge(setup_client)
    assert setup_client.get(f"{BASE}/state").json()["pending_step"] == "providers"

    setup_client.put(
        f"{BASE}/providers/generation",
        json={"provider": offerable_provider, "api_key": A_VALID_KEY},
    )
    assert setup_client.get(f"{BASE}/state").json()["pending_step"] == "providers"

    setup_client.put(
        f"{BASE}/providers/embeddings",
        json={"provider": offerable_provider, "api_key": A_VALID_KEY},
    )
    assert setup_client.get(f"{BASE}/state").json()["pending_step"] == "email"

    setup_client.post(f"{BASE}/email/skip")
    assert setup_client.get(f"{BASE}/state").json()["pending_step"] is None
