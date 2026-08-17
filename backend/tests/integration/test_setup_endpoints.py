"""The nine endpoints of `/setup/*`, checked against contracts/openapi.yaml.

The contract file is the design source and this reads it as data: for each
response, every property the schema declares `required` must be present, and
every field with an `enum` must carry one of its values. Asserting against the
document rather than against a copy of it in the test is what makes a drift
between them fail here instead of in the frontend's generated client.

Written before the endpoints exist, with an xfail per test naming the task that
turns it green (T058 disclosure, T059 providers, T060 email).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from app.domain.capability import (
    Capability,
    CapabilityUnverified,
    CredentialRejected,
    ProviderUnreachable,
    QuotaExceeded,
)
from app.domain.disclosure import CURRENT_DISCLOSURE
from tests.integration.conftest import (
    A_VALID_KEY,
    ConfigureCapability,
    MailboxDirector,
    ProbeDirector,
)

CONTRACT = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "001-candidate-onboarding"
    / "contracts"
    / "openapi.yaml"
)

BASE = "/api/v1/setup"


def schemas() -> dict[str, Any]:
    document = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    result: dict[str, Any] = document["components"]["schemas"]
    return result


def assert_satisfies(body: object, schema_name: str) -> None:
    """Every required property present, every enum value within its enum."""
    catalogue = schemas()
    schema = catalogue[schema_name]
    assert isinstance(body, dict), f"{schema_name} must arrive as an object"

    for field in schema.get("required", []):
        assert field in body, f"{schema_name}.{field} missing from the response"

    for field, declared in schema.get("properties", {}).items():
        if field not in body or body[field] is None:
            continue
        if "enum" in declared:
            assert body[field] in declared["enum"], (
                f"{schema_name}.{field} = {body[field]!r} is outside the contract's enum"
            )
        referenced = declared.get("$ref", "").rsplit("/", 1)[-1]
        if referenced in catalogue and isinstance(body[field], dict):
            assert_satisfies(body[field], referenced)


# ── divulgación (T058) ──────────────────────────────────────────────────────


@pytest.mark.xfail(strict=True, reason="verde en T058: GET /setup/state todavía no existe")
def test_state_answers_the_setup_state_schema(setup_client: TestClient) -> None:
    response = setup_client.get(f"{BASE}/state")

    assert response.status_code == 200
    assert_satisfies(response.json(), "SetupState")


@pytest.mark.xfail(strict=True, reason="verde en T058: GET /setup/state todavía no existe")
def test_a_fresh_installation_is_pending_on_the_disclosure(setup_client: TestClient) -> None:
    """Step zero: art. V puts it before any field to fill in (FR-001)."""
    body = setup_client.get(f"{BASE}/state").json()

    assert body["pending_step"] == "disclosure"
    assert body["disclosure_acknowledged"] is False
    assert body["is_complete"] is False


@pytest.mark.xfail(strict=True, reason="verde en T058: GET /setup/disclosure todavía no existe")
def test_the_disclosure_travels_whole_and_not_as_a_link(setup_client: TestClient) -> None:
    response = setup_client.get(f"{BASE}/disclosure")

    assert response.status_code == 200
    body = response.json()
    assert_satisfies(body, "Disclosure")
    assert body["body_md"] == CURRENT_DISCLOSURE.body_md
    assert body["acknowledged"] is False


@pytest.mark.xfail(strict=True, reason="verde en T058: el acuse todavía no se registra")
def test_the_acknowledgement_is_recorded_and_moves_the_step(setup_client: TestClient) -> None:
    response = setup_client.post(
        f"{BASE}/disclosure-acknowledgement",
        json={"disclosure_version": CURRENT_DISCLOSURE.version, "acknowledged": True},
    )

    assert response.status_code == 201
    body = response.json()
    assert_satisfies(body, "SetupState")
    assert body["disclosure_acknowledged"] is True
    assert body["disclosure_acknowledged_at"] is not None
    assert body["pending_step"] == "providers"


@pytest.mark.xfail(strict=True, reason="verde en T058: el acuse todavía no se registra")
def test_acknowledging_twice_is_refused(setup_client: TestClient) -> None:
    payload = {"disclosure_version": CURRENT_DISCLOSURE.version, "acknowledged": True}
    setup_client.post(f"{BASE}/disclosure-acknowledgement", json=payload)

    repeated = setup_client.post(f"{BASE}/disclosure-acknowledgement", json=payload)

    assert repeated.status_code == 409
    assert_satisfies(repeated.json(), "Error")


@pytest.mark.xfail(strict=True, reason="verde en T058: el acuse todavía no se registra")
def test_an_unacknowledged_flag_is_refused_by_the_contract(setup_client: TestClient) -> None:
    """`acknowledged` is `const: true`: continuing is not an acknowledgement (FR-002)."""
    response = setup_client.post(
        f"{BASE}/disclosure-acknowledgement",
        json={"disclosure_version": CURRENT_DISCLOSURE.version, "acknowledged": False},
    )

    assert response.status_code == 422


# ── proveedores (T059) ──────────────────────────────────────────────────────


@pytest.mark.xfail(strict=True, reason="verde en T059: el catálogo todavía no se expone")
def test_the_catalogue_answers_its_schema_for_both_capabilities(
    setup_client: TestClient,
) -> None:
    response = setup_client.get(f"{BASE}/providers/catalog")

    assert response.status_code == 200
    body = response.json()
    assert_satisfies(body, "ProviderCatalog")
    for capability in ("generation", "embeddings"):
        assert body[capability], f"the {capability} catalogue is empty"
        for option in body[capability]:
            assert_satisfies(option, "ProviderOption")


@pytest.mark.xfail(strict=True, reason="verde en T059: el catálogo todavía no se expone")
def test_the_cost_is_on_screen_before_any_key_is_asked_for(setup_client: TestClient) -> None:
    """FR-005: the figure travels with the option, not after the form."""
    body = setup_client.get(f"{BASE}/providers/catalog").json()

    for option in body["generation"]:
        assert "estimated_cost" in option
        assert option["estimated_cost"]["currency"] == "USD"


@pytest.mark.xfail(strict=True, reason="verde en T059: PUT /setup/providers todavía no existe")
def test_an_unconfigured_capability_answers_null(setup_client: TestClient) -> None:
    response = setup_client.get(f"{BASE}/providers/generation")

    assert response.status_code == 200
    assert response.json() is None


@pytest.mark.xfail(strict=True, reason="verde en T059: PUT /setup/providers todavía no existe")
def test_saving_a_working_key_verifies_the_capability(
    setup_client: TestClient, probes: ProbeDirector, offerable_provider: str
) -> None:
    response = setup_client.put(
        f"{BASE}/providers/generation",
        json={"provider": offerable_provider, "api_key": A_VALID_KEY},
    )

    assert response.status_code == 200
    body = response.json()
    assert_satisfies(body, "ProviderConfiguration")
    assert body["preflight"]["result"] == "verified"
    assert body["credential_status"] == "configured"
    assert body["is_usable"] is True


@pytest.mark.xfail(strict=True, reason="verde en T059: PUT /setup/providers todavía no existe")
def test_the_response_never_carries_the_key_that_was_sent(
    setup_client: TestClient, probes: ProbeDirector, offerable_provider: str
) -> None:
    """SC-013, on the one response where the key is in the request (FR-008)."""
    response = setup_client.put(
        f"{BASE}/providers/generation",
        json={"provider": offerable_provider, "api_key": A_VALID_KEY},
    )

    assert response.status_code == 200
    assert A_VALID_KEY not in response.text
    for length in (8, 16):
        assert A_VALID_KEY[:length] not in response.text


@pytest.mark.xfail(strict=True, reason="verde en T059: PUT /setup/providers todavía no existe")
@pytest.mark.parametrize(
    ("attempt", "status", "code"),
    [
        (CredentialRejected, 400, "PROVIDER_CREDENTIAL_REJECTED"),
        (QuotaExceeded, 429, "PROVIDER_QUOTA_EXCEEDED"),
        (ProviderUnreachable, 503, "PROVIDER_UNREACHABLE"),
    ],
)
def test_each_failing_result_has_its_own_status_and_code(
    setup_client: TestClient,
    probes: ProbeDirector,
    offerable_provider: str,
    attempt: type,
    status: int,
    code: str,
) -> None:
    """Four situations, four answers: never one flattened into another (R-23)."""
    probes.will_answer(
        Capability.GENERATION,
        attempt(capability=Capability.GENERATION, model="un-modelo"),
    )

    response = setup_client.put(
        f"{BASE}/providers/generation",
        json={"provider": offerable_provider, "api_key": A_VALID_KEY},
    )

    assert response.status_code == status
    assert response.json()["code"] == code
    assert_satisfies(response.json(), "Error")


@pytest.mark.xfail(strict=True, reason="verde en T059: PUT /setup/providers todavía no existe")
def test_a_provider_outside_the_closed_list_is_not_configurable(
    setup_client: TestClient,
) -> None:
    """FR-009: no arbitrary endpoint, and nothing unverified."""
    response = setup_client.put(
        f"{BASE}/providers/generation",
        json={"provider": "un-proveedor-inventado", "api_key": A_VALID_KEY},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "PROVIDER_NOT_OFFERED"


@pytest.mark.xfail(strict=True, reason="verde en T059: el acuse de degradación no existe")
def test_a_degraded_capability_needs_its_acknowledgement_to_become_usable(
    setup_client: TestClient, probes: ProbeDirector, offerable_provider: str
) -> None:
    """SC-016: what is lost is enumerated before it can be accepted."""
    probes.will_answer(
        Capability.GENERATION,
        CapabilityUnverified(capability=Capability.GENERATION, model="un-modelo"),
    )

    saved = setup_client.put(
        f"{BASE}/providers/generation",
        json={"provider": offerable_provider, "api_key": A_VALID_KEY},
    )
    assert saved.status_code == 200
    assert saved.json()["is_usable"] is False
    assert saved.json()["preflight"]["affected_features"], "the degradation was not enumerated"

    acknowledged = setup_client.post(f"{BASE}/providers/generation/degradation-acknowledgement")

    assert acknowledged.status_code == 201
    assert_satisfies(acknowledged.json(), "ProviderConfiguration")
    assert acknowledged.json()["is_usable"] is True


@pytest.mark.xfail(strict=True, reason="verde en T059: el acuse de degradación no existe")
def test_there_is_nothing_to_acknowledge_on_a_verified_capability(
    setup_client: TestClient, probes: ProbeDirector, configure: ConfigureCapability
) -> None:
    configure(setup_client, Capability.GENERATION, A_VALID_KEY)

    response = setup_client.post(f"{BASE}/providers/generation/degradation-acknowledgement")

    assert response.status_code == 409


# ── correo (T060) ───────────────────────────────────────────────────────────


@pytest.mark.xfail(strict=True, reason="verde en T060: GET /setup/email todavía no existe")
def test_the_email_step_answers_its_schema_with_the_disclosure_in_it(
    setup_client: TestClient,
) -> None:
    response = setup_client.get(f"{BASE}/email")

    assert response.status_code == 200
    body = response.json()
    assert_satisfies(body, "EmailStep")
    assert body["is_skippable"] is True
    assert body["status"] == "pending"


@pytest.mark.xfail(strict=True, reason="verde en T060: GET /setup/email todavía no existe")
def test_the_step_says_what_is_gained_and_what_is_not_lost(setup_client: TestClient) -> None:
    """FR-011: a decision needs both halves of the sentence."""
    body = setup_client.get(f"{BASE}/email").json()

    assert body["value_if_linked_es"]
    assert body["value_if_skipped_es"]
    assert body["oauth_docs_url"]


@pytest.mark.xfail(strict=True, reason="verde en T060: POST /setup/email/link todavía no existe")
def test_linking_verifies_the_label_before_believing_it(
    setup_client: TestClient, mailbox: MailboxDirector
) -> None:
    response = setup_client.post(
        f"{BASE}/email/link",
        json={
            "email_address": "candidata@example.com",
            "app_password": "abcd efgh ijkl mnop",
            "label": "Alertas de empleo",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert_satisfies(body, "EmailStep")
    assert body["status"] == "linked"
    assert body["label"] == "Alertas de empleo"


@pytest.mark.xfail(strict=True, reason="verde en T060: POST /setup/email/link todavía no existe")
def test_a_label_that_does_not_exist_leaves_the_step_pending(
    setup_client: TestClient, mailbox: MailboxDirector
) -> None:
    response = setup_client.post(
        f"{BASE}/email/link",
        json={
            "email_address": "candidata@example.com",
            "app_password": "abcd efgh ijkl mnop",
            "label": "Una etiqueta que no existe",
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "EMAIL_LABEL_NOT_FOUND"
    assert setup_client.get(f"{BASE}/email").json()["status"] == "pending"


@pytest.mark.xfail(strict=True, reason="verde en T060: POST /setup/email/skip todavía no existe")
def test_skipping_is_one_action_and_ends_the_step(setup_client: TestClient) -> None:
    response = setup_client.post(f"{BASE}/email/skip")

    assert response.status_code == 200
    assert_satisfies(response.json(), "SetupState")
    assert response.json()["email_status"] == "skipped"


@pytest.mark.xfail(strict=True, reason="verde en T060: POST /setup/email/link todavía no existe")
def test_no_response_of_the_email_step_carries_the_app_password(
    setup_client: TestClient, mailbox: MailboxDirector
) -> None:
    app_password = "abcd efgh ijkl mnop"

    linked = setup_client.post(
        f"{BASE}/email/link",
        json={
            "email_address": "candidata@example.com",
            "app_password": app_password,
            "label": "Alertas de empleo",
        },
    )
    read = setup_client.get(f"{BASE}/email")

    for response in (linked, read):
        assert response.status_code == 200
        assert app_password not in response.text
        assert "abcd" not in response.text
