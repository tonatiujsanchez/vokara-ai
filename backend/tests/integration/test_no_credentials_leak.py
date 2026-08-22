"""SC-013 audited over a full run: 0 appearances of a credential, anywhere.

The requirement is measured, not asserted in the abstract: the test walks a
first run that goes through the **four** preflight results and the mail step,
and then looks for the key — whole and in fragments — in every surface it could
have reached:

- the API responses,
- the structured log,
- the LLM traces,
- the error messages,
- and **every table of the database**, column by column.

Fragments matter as much as the whole: FR-008 says «ni completa ni
parcialmente», so a prefix of eight characters is a failure too. The fingerprint
of research R-24 is the one derived value allowed to exist, and it is checked to
contain no part of the key either.
"""

from __future__ import annotations

import io
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, inspect, text

from app.core.logging import configure_logging
from app.domain.capability import (
    Capability,
    CapabilityUnverified,
    CredentialRejected,
    ProviderUnreachable,
    QuotaExceeded,
)
from app.domain.disclosure import CURRENT_DISCLOSURE
from tests.integration.conftest import ProbeDirector

BASE = "/api/v1/setup"

GENERATION_KEY = "AIzaSyD-llave-de-generacion-para-la-auditoria"
EMBEDDINGS_KEY = "AIzaSyD-llave-de-embeddings-para-la-auditoria"
APP_PASSWORD = "abcd efgh ijkl mnop"

SECRETS = (GENERATION_KEY, EMBEDDINGS_KEY, APP_PASSWORD)
# Long enough not to collide with ordinary text, short enough that a truncated
# key would still be caught.
FRAGMENT_LENGTHS = (8, 12, 20)


@pytest.fixture
def captured_logs() -> Iterator[io.StringIO]:
    """Everything structlog emits during the run, in memory."""
    buffer = io.StringIO()
    configure_logging(stream=buffer)
    yield buffer
    configure_logging()


def fragments_of(secret: str) -> list[str]:
    return [secret[:length] for length in FRAGMENT_LENGTHS] + [
        secret[-length:] for length in FRAGMENT_LENGTHS
    ]


def assert_clean(surface: str, where: str) -> None:
    for secret in SECRETS:
        assert secret not in surface, f"a credential reached {where}"
        for fragment in fragments_of(secret):
            assert fragment not in surface, f"a fragment of a credential reached {where}"


def walk_the_whole_first_run(client: TestClient, probes: ProbeDirector, provider: str) -> list[str]:
    """Acknowledgement, the four results, the mail step. Returns every response body."""
    bodies: list[str] = []

    def put(capability: Capability, key: str) -> None:
        response = client.put(
            f"{BASE}/providers/{capability.value}",
            json={"provider": provider, "api_key": key},
        )
        bodies.append(response.text)

    bodies.append(
        client.post(
            f"{BASE}/disclosure-acknowledgement",
            json={"disclosure_version": CURRENT_DISCLOSURE.version, "acknowledged": True},
        ).text
    )

    for attempt in (CredentialRejected, QuotaExceeded, ProviderUnreachable, CapabilityUnverified):
        probes.will_answer(
            Capability.GENERATION,
            attempt(capability=Capability.GENERATION, model="un-modelo"),
        )
        put(Capability.GENERATION, GENERATION_KEY)

    bodies.append(client.post(f"{BASE}/providers/generation/degradation-acknowledgement").text)

    probes.answers.pop(Capability.GENERATION, None)
    put(Capability.GENERATION, GENERATION_KEY)
    put(Capability.EMBEDDINGS, EMBEDDINGS_KEY)

    bodies.append(
        client.post(
            f"{BASE}/email/link",
            json={
                "email_address": "candidata@example.com",
                "app_password": APP_PASSWORD,
                "label": "Alertas de empleo",
            },
        ).text
    )

    for path in ("state", "disclosure", "providers/catalog", "providers/generation", "email"):
        bodies.append(client.get(f"{BASE}/{path}").text)

    return bodies


def test_no_response_of_a_full_first_run_carries_a_credential(
    setup_client: TestClient,
    probes: ProbeDirector,
    mailbox: object,
    offerable_provider: str,
) -> None:
    """The four results and the mail step, checked on the way out (SC-013)."""
    bodies = walk_the_whole_first_run(setup_client, probes, offerable_provider)

    for body in bodies:
        assert_clean(body, "an API response")


def test_nothing_of_a_credential_reaches_the_log_or_a_trace(
    setup_client: TestClient,
    probes: ProbeDirector,
    mailbox: object,
    offerable_provider: str,
    captured_logs: io.StringIO,
) -> None:
    """The log is where a leak is cheapest to cause and hardest to notice."""
    walk_the_whole_first_run(setup_client, probes, offerable_provider)

    assert_clean(captured_logs.getvalue(), "the structured log")


def test_no_table_of_the_database_holds_a_credential(
    setup_client: TestClient,
    probes: ProbeDirector,
    mailbox: object,
    offerable_provider: str,
    db_engine: Engine,
) -> None:
    """Every table, every column: FR-008 is about the database above all."""
    walk_the_whole_first_run(setup_client, probes, offerable_provider)

    tables = inspect(db_engine).get_table_names()
    assert tables, "the schema is empty: this test would pass without checking anything"

    with db_engine.begin() as connection:
        for table in tables:
            rows = connection.execute(text(f'select * from "{table}"')).fetchall()  # noqa: S608
            assert_clean(" ".join(str(value) for row in rows for value in row), f"table {table}")


def test_the_fingerprint_that_is_stored_contains_no_part_of_the_key(
    setup_client: TestClient,
    probes: ProbeDirector,
    offerable_provider: str,
    db_engine: Engine,
) -> None:
    """The one derived value allowed to exist, checked as carefully (R-24)."""
    setup_client.post(
        f"{BASE}/disclosure-acknowledgement",
        json={"disclosure_version": CURRENT_DISCLOSURE.version, "acknowledged": True},
    )
    setup_client.put(
        f"{BASE}/providers/generation",
        json={"provider": offerable_provider, "api_key": GENERATION_KEY},
    )

    with db_engine.begin() as connection:
        stored = (
            connection.execute(text("select credential_fingerprint from provider_configurations"))
            .scalars()
            .all()
        )

    assert stored, "nothing was stored: the walk did not reach the database"
    for fingerprint in stored:
        assert_clean(fingerprint, "the stored fingerprint")


def test_the_key_is_written_to_local_configuration_and_not_to_the_database(
    setup_client: TestClient,
    probes: ProbeDirector,
    offerable_provider: str,
    data_dir: object,
) -> None:
    """Where it *does* live, so the absence elsewhere is not a false negative."""
    from app.core.config import get_settings
    from app.core.credentials import WizardCredential, read_credential

    setup_client.post(
        f"{BASE}/disclosure-acknowledgement",
        json={"disclosure_version": CURRENT_DISCLOSURE.version, "acknowledged": True},
    )
    setup_client.put(
        f"{BASE}/providers/generation",
        json={"provider": offerable_provider, "api_key": GENERATION_KEY},
    )

    stored = read_credential(WizardCredential.GENERATION_API_KEY, get_settings())

    assert stored is not None
    assert stored.get_secret_value() == GENERATION_KEY
