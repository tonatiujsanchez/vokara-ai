"""The one place where a provider identifier becomes an implementation.

Every other module asks for a **capability** and receives a port. This one
knows names, and it is the only module besides `capabilities.py` allowed to —
which is what makes the guard in
`tests/architecture/test_provider_name_isolation.py` a real boundary and not a
convention (art. XI, ADR-011).

The credential, the endpoint and the model name are resolved **here**, from
`Settings`, and never appear in a port signature. That is the whole reason
adding Ollama — or any OpenAI-compatible server — is a new entry in the
registry below plus an implementation of the port, rather than a refactor of
everything behind it (ADR-011 decision 5, research R-25).

Model names come from configuration with an environment override, so a provider
retiring a model cannot break an installation the user has not updated. Google
retired `gemini-2.0-flash` on 1 June 2026, which is the concrete event this
rule exists for (ADR-011).
"""

from __future__ import annotations

from app.adapters.llm.base import CapabilityProbePort, EmbeddingsPort, StructuredOutputPort
from app.adapters.llm.capabilities import ProviderId, offerable_for
from app.adapters.llm.google import GoogleEmbeddings, GoogleStructuredOutput
from app.core.config import Settings
from app.domain.capability import Capability


class ProviderNotImplementedError(LookupError):
    """Asked for a provider of the closed list that has no implementation yet.

    Not a message for the candidate: the catalogue only offers verified
    providers (FR-009), so reaching this is a programming error, not something
    a user can do from the wizard.
    """

    def __init__(self, provider: ProviderId, capability: Capability) -> None:
        super().__init__(f"no {capability.value} implementation for provider {provider.value}")
        self.provider = provider
        self.capability = capability


def _google_generation(settings: Settings) -> GoogleStructuredOutput:
    return GoogleStructuredOutput(
        model=settings.google_model,
        credential=settings.google_api_key,
    )


def _google_embeddings(settings: Settings) -> GoogleEmbeddings:
    return GoogleEmbeddings(
        model=settings.google_embed,
        dimensions=settings.embedding_dimensions,
        credential=settings.google_api_key,
    )


def build_structured_output(provider: ProviderId, settings: Settings) -> StructuredOutputPort:
    """The generation port of a provider, with its own credential and model."""
    if provider is not ProviderId.GOOGLE:
        raise ProviderNotImplementedError(provider, Capability.GENERATION)
    return _google_generation(settings)


def build_embeddings(provider: ProviderId, settings: Settings) -> EmbeddingsPort:
    """The embeddings port, configured independently of generation (FR-004)."""
    if provider is not ProviderId.GOOGLE:
        raise ProviderNotImplementedError(provider, Capability.EMBEDDINGS)
    return _google_embeddings(settings)


def build_probe(
    provider: ProviderId, capability: Capability, settings: Settings
) -> CapabilityProbePort:
    """The preflight probe for one capability of one provider (FR-006).

    It returns the same object that will serve the capability afterwards, so
    what gets verified is what gets used: verifying one client and then calling
    a differently configured one would make the preflight a formality.
    """
    if provider is not ProviderId.GOOGLE:
        raise ProviderNotImplementedError(provider, capability)

    match capability:
        case Capability.GENERATION:
            return _google_generation(settings)
        case Capability.EMBEDDINGS:
            return _google_embeddings(settings)


def is_implemented(provider: ProviderId) -> bool:
    """Whether an implementation exists, which is not whether it is offerable.

    A row can be verified empirically and still have no code behind it; the
    catalogue comes from `capabilities.py` and this answers the other half.
    """
    return provider is ProviderId.GOOGLE


def implemented_and_offerable(capability: Capability) -> tuple[ProviderId, ...]:
    """What the wizard can actually hand the user for a capability."""
    return tuple(row.provider for row in offerable_for(capability) if is_implemented(row.provider))
