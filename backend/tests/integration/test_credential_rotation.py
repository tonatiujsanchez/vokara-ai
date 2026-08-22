"""Rotating a key invalidates its preflight, and nothing else (research R-24).

The credential lives in local configuration and the preflight result lives in
the database: two places that diverge the moment someone edits a file, which in
a local application is the natural thing to do. Without detection, a stored
«verificada» would go on describing a key that is no longer there — a result
that lies, and the silent way SC-012 breaks.

The rotation here is done the way a user would do it: by editing the file, not
by calling an endpoint. That is the whole point — the application has to notice
a change it was not told about.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import get_settings
from app.core.credentials import (
    WizardCredential,
    api_key_of,
    forget_credential,
    write_credential,
)
from app.domain.capability import Capability
from app.domain.disclosure import CURRENT_DISCLOSURE
from tests.integration.conftest import A_VALID_KEY, ProbeDirector

BASE = "/api/v1/setup"
ANOTHER_KEY = "AIzaSyD-la-llave-que-el-usuario-pego-despues"


def configure_both(client: TestClient, provider: str) -> None:
    client.post(
        f"{BASE}/disclosure-acknowledgement",
        json={"disclosure_version": CURRENT_DISCLOSURE.version, "acknowledged": True},
    )
    for capability in Capability:
        client.put(
            f"{BASE}/providers/{capability.value}",
            json={"provider": provider, "api_key": A_VALID_KEY},
        )


def rotate(capability: Capability, key: str) -> None:
    """What the candidate does: replace the value in local configuration."""
    write_credential(api_key_of(capability), SecretStr(key), get_settings())


def test_rotating_one_key_invalidates_only_that_capability(
    setup_client: TestClient, probes: ProbeDirector, offerable_provider: str
) -> None:
    configure_both(setup_client, offerable_provider)

    rotate(Capability.GENERATION, ANOTHER_KEY)

    state = setup_client.get(f"{BASE}/state").json()
    assert state["providers"]["generation"]["is_usable"] is False
    assert state["providers"]["generation"]["credential_status"] == "not_configured"
    assert state["providers"]["embeddings"]["is_usable"] is True
    assert state["providers"]["embeddings"]["credential_status"] == "configured"


def test_the_acknowledgement_survives_a_rotation(
    setup_client: TestClient, probes: ProbeDirector, offerable_provider: str
) -> None:
    """FR-014: what was accepted is not re-asked because a key changed."""
    configure_both(setup_client, offerable_provider)

    rotate(Capability.GENERATION, ANOTHER_KEY)

    state = setup_client.get(f"{BASE}/state").json()
    assert state["disclosure_acknowledged"] is True
    assert state["pending_step"] == "providers"


def test_removing_the_key_altogether_also_invalidates_the_preflight(
    setup_client: TestClient, probes: ProbeDirector, offerable_provider: str
) -> None:
    """No credential is not the same as a bad one, but it is not verified either."""
    configure_both(setup_client, offerable_provider)

    forget_credential(WizardCredential.GENERATION_API_KEY, get_settings())

    generation = setup_client.get(f"{BASE}/providers/generation").json()
    assert generation["credential_status"] == "not_configured"
    assert generation["is_usable"] is False


def test_saving_the_rotated_key_verifies_it_again(
    setup_client: TestClient, probes: ProbeDirector, offerable_provider: str
) -> None:
    """The way out is the wizard, and it is one step: paste and save."""
    configure_both(setup_client, offerable_provider)
    rotate(Capability.GENERATION, ANOTHER_KEY)

    response = setup_client.put(
        f"{BASE}/providers/generation",
        json={"provider": offerable_provider, "api_key": ANOTHER_KEY},
    )

    assert response.status_code == 200
    assert response.json()["is_usable"] is True
    assert setup_client.get(f"{BASE}/state").json()["providers"]["generation"]["is_usable"] is True


def test_a_rotation_after_the_first_run_never_locks_the_onboarding_out(
    setup_client: TestClient, probes: ProbeDirector, offerable_provider: str
) -> None:
    """FR-010: a changed embeddings key degrades, it does not reopen the wizard."""
    configure_both(setup_client, offerable_provider)
    setup_client.post(f"{BASE}/email/skip")

    rotate(Capability.EMBEDDINGS, ANOTHER_KEY)

    state = setup_client.get(f"{BASE}/state").json()
    assert state["providers"]["embeddings"]["is_usable"] is False
    assert state["pending_step"] is None
    assert state["is_complete"] is True


def test_the_same_key_saved_twice_is_not_a_rotation(
    setup_client: TestClient, probes: ProbeDirector, offerable_provider: str
) -> None:
    """The comparison has to be stable, or every read would look like a change."""
    configure_both(setup_client, offerable_provider)

    rotate(Capability.GENERATION, A_VALID_KEY)

    assert setup_client.get(f"{BASE}/providers/generation").json()["is_usable"] is True
