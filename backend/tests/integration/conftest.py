"""Fixtures for the first-run endpoints: a real database, a fake provider.

Real Postgres, because what these tests exercise is persistence and the
constraints under it. A fake provider, because the preflight is a real call to
somebody's paid API: probing it for real in CI would cost money, need a
credential nobody should have to publish, and fail whenever the network does.
The double drives the four results instead, which is the only way SC-012 and
SC-016 can be verified at all (research R-23).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.adapters.email.base import EmailFailure, EmailPort, EmailPortError
from app.adapters.llm.capabilities import ProviderId
from app.core.config import Settings, get_settings
from app.db.session import get_engine, get_session_factory
from app.domain.capability import Capability, PreflightAttempt, Verified
from app.main import app
from app.services import email_link_service, preflight_service

A_VALID_KEY = "AIzaSyD-una-llave-de-prueba-que-no-existe"


class FakeProbe:
    """A provider that answers whatever the test needs it to answer."""

    def __init__(self, capability: Capability, attempt: PreflightAttempt) -> None:
        self._capability = capability
        self._attempt = attempt

    @property
    def capability(self) -> Capability:
        return self._capability

    async def probe(self) -> PreflightAttempt:
        return self._attempt


class ProbeDirector:
    """Decides what each capability's probe will answer, per test."""

    def __init__(self) -> None:
        self.answers: dict[Capability, PreflightAttempt] = {}
        self.credentials: dict[Capability, SecretStr | None] = {}
        self.models: dict[Capability, str | None] = {}

    def will_answer(self, capability: Capability, attempt: PreflightAttempt) -> None:
        self.answers[capability] = attempt

    def build(
        self,
        provider: ProviderId,
        capability: Capability,
        settings: Settings,
        credential: SecretStr | None = None,
        model: str | None = None,
    ) -> FakeProbe:
        self.credentials[capability] = credential
        self.models[capability] = model
        default = Verified(
            capability=capability,
            model=model or "un-modelo",
            embedding_dim=768 if capability is Capability.EMBEDDINGS else None,
        )
        return FakeProbe(capability, self.answers.get(capability, default))


class FakeEmailPort:
    """A mailbox whose labels the test decides, without a network."""

    def __init__(self, labels: tuple[str, ...], failure: EmailFailure | None = None) -> None:
        self._labels = labels
        self._failure = failure

    def verify_label(self, label: str) -> None:
        if self._failure is not None:
            raise EmailPortError(self._failure)
        if label not in self._labels:
            raise EmailPortError(EmailFailure.LABEL_NOT_FOUND)


class MailboxDirector:
    """Decides what the mailbox looks like, per test."""

    def __init__(self) -> None:
        self.labels: tuple[str, ...] = ("Alertas de empleo",)
        self.failure: EmailFailure | None = None
        self.credentials: list[SecretStr] = []

    def will_fail_with(self, failure: EmailFailure) -> None:
        self.failure = failure

    def build(self, address: str, credential: SecretStr) -> EmailPort:
        self.credentials.append(credential)
        return FakeEmailPort(self.labels, self.failure)


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A throwaway data directory, so no test writes a credential in the repo."""
    directory = tmp_path / "data"
    monkeypatch.setenv("VOKARA_DATA_DIR", str(directory))
    get_settings.cache_clear()
    yield directory
    get_settings.cache_clear()


@pytest.fixture
def probes(monkeypatch: pytest.MonkeyPatch) -> ProbeDirector:
    director = ProbeDirector()
    monkeypatch.setattr(preflight_service, "build_probe", director.build)
    return director


@pytest.fixture
def mailbox(monkeypatch: pytest.MonkeyPatch) -> MailboxDirector:
    director = MailboxDirector()
    monkeypatch.setattr(email_link_service, "_build_port", director.build)
    return director


@pytest.fixture
def setup_client(migrated_database: str, data_dir: Path) -> Iterator[TestClient]:
    """The API against the throwaway database and the throwaway data directory."""
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    with TestClient(app) as client:
        yield client
    get_engine.cache_clear()
    get_session_factory.cache_clear()


@pytest.fixture
def offerable_provider() -> str:
    """The first provider the catalogue offers, whoever it happens to be.

    Reading it from the catalogue instead of writing a name is the same rule the
    frontend follows: nothing here branches on who the provider is (art. XI).
    """
    from app.services.provider_catalog_service import options_for

    return options_for(Capability.GENERATION)[0].provider


ConfigureCapability = Callable[[TestClient, Capability, str], None]


@pytest.fixture
def configure(offerable_provider: str) -> ConfigureCapability:
    """Walk a capability through the wizard the way the SPA would."""

    def run(client: TestClient, capability: Capability, api_key: str = A_VALID_KEY) -> None:
        response = client.put(
            f"/api/v1/setup/providers/{capability.value}",
            json={"provider": offerable_provider, "api_key": api_key},
        )
        assert response.status_code in {200, 400, 429, 503}, response.text

    return run
