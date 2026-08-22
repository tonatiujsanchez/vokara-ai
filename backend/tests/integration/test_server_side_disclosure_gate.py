"""SC-011: the disclosure gate lives in the server, not in the guard of the SPA.

The first run has a convenience guard in the SPA — it keeps `/onboarding`
unreachable while a step is pending — and that guard is not the gate. Article V
asks that *no* route reach an upload without the acknowledgement on record:
direct navigation, a reload, a restart, or a `curl` straight at the API, with no
frontend involved at all. A check that only the SPA performs would pass every
one of those except the last, which is the only one an attacker or a curious
user actually takes.

`setup_service.require_disclosure_acknowledgement()` is that gate. Until the
upload endpoint of T086 exists it has no caller, so this file gives it one: a
probe route, protected exactly the way `POST /documents` will be, exercised over
real HTTP against a real database. What is under test is the gate and the shape
of its refusal — never the probe, which exists only to be refused.

The check the Checkpoint B bullet originally named — `POST /documents` with curl
— returns in Checkpoint C, once that route exists. This is the same property,
verified at the layer where it is decided rather than at a route that has not
been written yet.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.api.deps import CandidateId
from app.api.errors import error_responses
from app.db.session import get_engine, get_session_factory
from app.domain.disclosure import CURRENT_DISCLOSURE
from app.domain.errors import DisclosureAcknowledgementRequiredError, ErrorCode
from app.main import create_app
from app.services import setup_service
from tests.integration.conftest import _forget_the_first_run

CONTRACT = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "001-candidate-onboarding"
    / "contracts"
    / "openapi.yaml"
)

PROBE = "/api/v1/gated-probe"


def build_gated_app() -> FastAPI:
    """The real application plus one route behind the gate T086 will use.

    Declared with the same `responses=` the upload endpoint will declare, so the
    refusal this test sees is the refusal the contract describes.
    """
    app = create_app()

    @app.post(
        PROBE,
        responses=error_responses(DisclosureAcknowledgementRequiredError),
        summary="Ruta de prueba: solo existe para ser rechazada sin acuse",
    )
    def gated_probe(candidate_id: CandidateId) -> dict[str, bool]:
        setup_service.require_disclosure_acknowledgement(candidate_id)
        return {"reached": True}

    return app


@pytest.fixture
def gated_client(migrated_database: str, data_dir: Path, db_engine: Engine) -> Iterator[TestClient]:
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    _forget_the_first_run(db_engine)
    with TestClient(build_gated_app()) as client:
        yield client
    _forget_the_first_run(db_engine)
    get_engine.cache_clear()
    get_session_factory.cache_clear()


def acknowledge(client: TestClient) -> None:
    """Walk the disclosure step the way the SPA would."""
    response = client.post(
        "/api/v1/setup/disclosure-acknowledgement",
        json={"disclosure_version": CURRENT_DISCLOSURE.version, "acknowledged": True},
    )
    assert response.status_code == 201


def test_without_an_acknowledgement_the_server_refuses_with_409(
    gated_client: TestClient,
) -> None:
    """The gate of SC-011, over HTTP, on a clean installation."""
    response = gated_client.post(PROBE)

    assert response.status_code == 409
    assert response.json()["code"] == ErrorCode.DISCLOSURE_ACKNOWLEDGEMENT_REQUIRED.value


def test_the_refusal_has_the_shape_the_design_contract_declares(
    gated_client: TestClient,
) -> None:
    """Read from `contracts/openapi.yaml` rather than from a copy of it here."""
    document: dict[str, Any] = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    schema = document["components"]["schemas"]["Error"]

    body = gated_client.post(PROBE).json()

    for field in schema["required"]:
        assert field in body, f"Error.{field} missing from the refusal"
    assert body["code"] in schema["properties"]["code"]["enum"]
    assert isinstance(body["message"], str)
    assert body["message"]


def test_the_refusal_carries_no_credential_and_no_technical_trace(
    gated_client: TestClient,
) -> None:
    """The rules of contracts/errors.md hold on the gate too (FR-008, roadmap §11.5)."""
    body = gated_client.post(PROBE).text

    for marker in ("Traceback", "sqlalchemy", 'File "', "0x"):
        assert marker not in body


def test_the_gate_reads_the_record_and_not_the_request(gated_client: TestClient) -> None:
    """Nothing a client sends can stand in for the acknowledgement.

    FR-003 keeps `candidate_id` out of every request, and FR-002 makes the
    acknowledgement a persisted fact. A caller cannot assert either one.
    """
    forged = gated_client.post(
        PROBE,
        json={"acknowledged": True, "disclosure_version": CURRENT_DISCLOSURE.version},
        headers={"X-Disclosure-Acknowledged": "true"},
    )

    assert forged.status_code == 409


def test_with_the_acknowledgement_on_record_the_route_is_reached(
    gated_client: TestClient,
) -> None:
    """The gate refuses an absence, not every request: FR-015 must be reachable."""
    acknowledge(gated_client)

    response = gated_client.post(PROBE)

    assert response.status_code == 200
    assert response.json() == {"reached": True}


def test_an_acknowledgement_of_an_older_text_does_not_open_the_gate(
    gated_client: TestClient,
) -> None:
    """R-29: a yes to a different text is not a yes to this one."""
    stale = gated_client.post(
        "/api/v1/setup/disclosure-acknowledgement",
        json={"disclosure_version": "1970-01-01", "acknowledged": True},
    )

    assert stale.status_code == 409
    assert gated_client.post(PROBE).status_code == 409
