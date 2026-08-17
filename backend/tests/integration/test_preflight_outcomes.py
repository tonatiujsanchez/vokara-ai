"""The four results of FR-007, each with its message and its consequence.

They are four situations, so they get four answers. The one that costs money to
confuse is quota with credential: telling someone their key is wrong when the
key works sends them to regenerate a perfectly good one (research R-23), so that
distinction is asserted twice — in the status and in the text.

`provider_unreachable` is here too, as the fifth case that is **not** a result
about the capability: nothing is persisted for it, because a stored «sin
verificar» would be a claim about a provider nobody managed to ask.
"""

from __future__ import annotations

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.domain.capability import (
    Capability,
    CapabilityUnverified,
    CredentialRejected,
    ProviderUnreachable,
    QuotaExceeded,
    Verified,
)
from app.domain.disclosure import CURRENT_DISCLOSURE
from tests.integration.conftest import A_VALID_KEY, ProbeDirector

BASE = "/api/v1/setup"


def acknowledge(client: TestClient) -> None:
    client.post(
        f"{BASE}/disclosure-acknowledgement",
        json={"disclosure_version": CURRENT_DISCLOSURE.version, "acknowledged": True},
    )


def save(
    client: TestClient, provider: str, capability: Capability = Capability.GENERATION
) -> httpx.Response:
    response: httpx.Response = client.put(
        f"{BASE}/providers/{capability.value}",
        json={"provider": provider, "api_key": A_VALID_KEY},
    )
    return response


def test_verified_generation_becomes_usable_and_moves_the_wizard_on(
    setup_client: TestClient, probes: ProbeDirector, offerable_provider: str
) -> None:
    acknowledge(setup_client)

    body = save(setup_client, offerable_provider).json()

    assert body["preflight"]["result"] == "verified"
    assert body["is_usable"] is True
    assert "verificada" in body["preflight"]["message"]
    assert setup_client.get(f"{BASE}/state").json()["pending_step"] == "providers"


def test_verified_embeddings_records_the_dimension_it_observed(
    setup_client: TestClient, probes: ProbeDirector, offerable_provider: str
) -> None:
    """FR-007.2: that number ends up beside every future vector (ADR-003)."""
    acknowledge(setup_client)
    probes.will_answer(
        Capability.EMBEDDINGS,
        Verified(capability=Capability.EMBEDDINGS, model="un-modelo", embedding_dim=768),
    )

    body = save(setup_client, offerable_provider, Capability.EMBEDDINGS).json()

    assert body["preflight"]["embedding_dim"] == 768


def test_a_rejected_credential_does_not_advance_and_shows_where_to_regenerate(
    setup_client: TestClient, probes: ProbeDirector, offerable_provider: str
) -> None:
    """FR-007.1: no key on screen, no stack trace, no progress."""
    acknowledge(setup_client)
    probes.will_answer(
        Capability.GENERATION,
        CredentialRejected(capability=Capability.GENERATION, model="un-modelo"),
    )

    response = save(setup_client, offerable_provider)

    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "PROVIDER_CREDENTIAL_REJECTED"
    assert body["details"]["console_url"].startswith("https://")
    assert A_VALID_KEY not in response.text

    state = setup_client.get(f"{BASE}/state").json()
    assert state["pending_step"] == "providers"
    assert state["providers"]["generation"]["credential_status"] == "rejected"
    assert state["providers"]["generation"]["is_usable"] is False


def test_an_exhausted_quota_is_never_presented_as_an_invalid_key(
    setup_client: TestClient, probes: ProbeDirector, offerable_provider: str
) -> None:
    """FR-007.4, and the confusion with the most concrete cost to the candidate."""
    acknowledge(setup_client)
    probes.will_answer(
        Capability.GENERATION,
        QuotaExceeded(capability=Capability.GENERATION, model="un-modelo"),
    )

    response = save(setup_client, offerable_provider)

    assert response.status_code == 429
    assert response.json()["code"] == "PROVIDER_QUOTA_EXCEEDED"
    assert "válida" in response.json()["message"]
    assert "rechazó" not in response.json()["message"]

    generation = setup_client.get(f"{BASE}/providers/generation").json()
    assert generation["preflight"]["result"] == "quota_exceeded"
    assert generation["is_usable"] is False


def test_a_capability_without_guarantee_enumerates_what_is_lost_before_asking(
    setup_client: TestClient, probes: ProbeDirector, offerable_provider: str
) -> None:
    """SC-016: 0 degradations discovered after configuring."""
    acknowledge(setup_client)
    probes.will_answer(
        Capability.GENERATION,
        CapabilityUnverified(capability=Capability.GENERATION, model="un-modelo"),
    )

    saved = save(setup_client, offerable_provider).json()

    assert saved["preflight"]["result"] == "capability_unverified"
    assert saved["is_usable"] is False
    features = saved["preflight"]["affected_features"]
    assert [feature["code"] for feature in features] == ["CV_PARSING"]
    assert features[0]["message"]

    acknowledged = setup_client.post(
        f"{BASE}/providers/generation/degradation-acknowledgement"
    ).json()

    assert acknowledged["is_usable"] is True
    assert acknowledged["degradation_acknowledged_at"] is not None


def test_an_unreachable_provider_persists_nothing_and_says_so(
    setup_client: TestClient,
    probes: ProbeDirector,
    offerable_provider: str,
    db_engine: Engine,
) -> None:
    """A row saying «unverified» would be a claim about a provider never asked."""
    acknowledge(setup_client)
    probes.will_answer(
        Capability.GENERATION,
        ProviderUnreachable(capability=Capability.GENERATION, model="un-modelo"),
    )

    response = save(setup_client, offerable_provider)

    assert response.status_code == 503
    assert response.json()["code"] == "PROVIDER_UNREACHABLE"
    assert "no hace falta que vuelvas a escribirla" in response.json()["message"]
    assert setup_client.get(f"{BASE}/providers/generation").json() is None

    with db_engine.begin() as connection:
        rows = connection.execute(text("select count(*) from provider_configurations")).scalar_one()
    assert rows == 0


def test_the_embeddings_result_never_decides_the_generation_one(
    setup_client: TestClient, probes: ProbeDirector, offerable_provider: str
) -> None:
    """FR-004: two independent choices, verified separately with their own key."""
    acknowledge(setup_client)
    probes.will_answer(
        Capability.EMBEDDINGS,
        CredentialRejected(capability=Capability.EMBEDDINGS, model="un-modelo"),
    )

    save(setup_client, offerable_provider, Capability.GENERATION)
    save(setup_client, offerable_provider, Capability.EMBEDDINGS)

    state = setup_client.get(f"{BASE}/state").json()
    assert state["providers"]["generation"]["is_usable"] is True
    assert state["providers"]["embeddings"]["is_usable"] is False


def test_missing_embeddings_never_blocks_the_end_of_the_first_run(
    setup_client: TestClient, probes: ProbeDirector, offerable_provider: str
) -> None:
    """FR-010: it degrades explicitly, it does not block."""
    acknowledge(setup_client)
    save(setup_client, offerable_provider, Capability.GENERATION)

    setup_client.post(f"{BASE}/email/skip")

    state = setup_client.get(f"{BASE}/state").json()
    assert state["providers"]["embeddings"] is None
    assert state["pending_step"] is None
    assert state["is_complete"] is True
