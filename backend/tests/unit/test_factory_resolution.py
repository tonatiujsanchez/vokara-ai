"""The factory resolves ports from configuration, and refuses what it cannot serve.

The interesting assertions are the negative ones: that the credential comes
from `Settings` and never from an argument, that an unverified provider gets no
implementation, and that what the preflight verifies is the very object that
will later be used (FR-006, FR-009, ADR-011).
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from app.adapters.llm.base import CapabilityProbePort, EmbeddingsPort, StructuredOutputPort
from app.adapters.llm.capabilities import ProviderId
from app.adapters.llm.factory import (
    ProviderNotImplementedError,
    build_embeddings,
    build_probe,
    build_structured_output,
    implemented_and_offerable,
    is_implemented,
)
from app.core.config import Settings
from app.domain.capability import Capability

UNIMPLEMENTED = [
    ProviderId.OPENAI,
    ProviderId.ANTHROPIC,
    ProviderId.DEEPSEEK,
    ProviderId.MOONSHOT,
]


@pytest.fixture
def settings() -> Settings:
    return Settings(
        google_api_key=SecretStr("a-local-credential"),
        google_model="a-configured-generation-model",
        google_embed="a-configured-embeddings-model",
        embedding_dimensions=768,
    )


def test_the_generation_port_is_built_from_configuration(settings: Settings) -> None:
    port = build_structured_output(ProviderId.GOOGLE, settings)

    assert isinstance(port, StructuredOutputPort)
    assert port.model_name == "a-configured-generation-model"  # type: ignore[attr-defined]


def test_the_embeddings_port_carries_the_dimension_configuration_asks_for(
    settings: Settings,
) -> None:
    port = build_embeddings(ProviderId.GOOGLE, settings)

    assert isinstance(port, EmbeddingsPort)
    assert port.model_name == "a-configured-embeddings-model"
    assert port.dimensions == 768


def test_the_two_capabilities_resolve_to_two_independent_objects(settings: Settings) -> None:
    """FR-004: neither choice conditions the other, not even in the wiring."""
    generation = build_structured_output(ProviderId.GOOGLE, settings)
    embeddings = build_embeddings(ProviderId.GOOGLE, settings)

    assert id(generation) != id(embeddings)
    assert generation.model_name != embeddings.model_name  # type: ignore[attr-defined]


@pytest.mark.parametrize("capability", list(Capability))
def test_the_probe_is_the_object_that_will_serve_the_capability(
    capability: Capability, settings: Settings
) -> None:
    probe = build_probe(ProviderId.GOOGLE, capability, settings)

    assert isinstance(probe, CapabilityProbePort)
    assert probe.capability is capability


@pytest.mark.parametrize("provider", UNIMPLEMENTED)
def test_a_provider_without_an_implementation_is_refused(provider: ProviderId) -> None:
    """FR-009: nothing unverified gets built, however tempting the name is."""
    settings = Settings()

    with pytest.raises(ProviderNotImplementedError) as raised:
        build_structured_output(provider, settings)

    assert raised.value.provider is provider
    assert not is_implemented(provider)


@pytest.mark.parametrize("provider", UNIMPLEMENTED)
def test_the_refusal_covers_every_entry_point(provider: ProviderId) -> None:
    settings = Settings()

    with pytest.raises(ProviderNotImplementedError):
        build_embeddings(provider, settings)
    with pytest.raises(ProviderNotImplementedError):
        build_probe(provider, Capability.GENERATION, settings)


def test_the_refusal_says_nothing_a_candidate_would_ever_read() -> None:
    """The catalogue never offers it, so this is a bug report, not a message."""
    error = ProviderNotImplementedError(ProviderId.OPENAI, Capability.EMBEDDINGS)

    assert isinstance(error, LookupError)
    assert str(error) == "no embeddings implementation for provider openai"


@pytest.mark.parametrize("capability", list(Capability))
def test_only_a_verified_provider_with_code_behind_it_is_offered(
    capability: Capability,
) -> None:
    assert implemented_and_offerable(capability) == (ProviderId.GOOGLE,)


def test_a_port_never_receives_the_credential_as_an_argument(settings: Settings) -> None:
    """It is configuration of the implementation, resolved here (R-25)."""
    import inspect

    port = build_structured_output(ProviderId.GOOGLE, settings)
    parameters = inspect.signature(port.generate).parameters

    assert not [name for name in parameters if "key" in name or "credential" in name]


def test_a_missing_credential_is_not_an_error_at_build_time() -> None:
    """Nothing may assume there is an API key — that is what opens the door to
    a local server later (ADR-011 decision 5)."""
    port = build_structured_output(ProviderId.GOOGLE, Settings(google_api_key=None))

    assert isinstance(port, StructuredOutputPort)
