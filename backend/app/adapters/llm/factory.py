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

from pydantic import SecretStr

from app.adapters.llm.base import CapabilityProbePort, EmbeddingsPort, StructuredOutputPort
from app.adapters.llm.capabilities import ProviderId, offerable_for
from app.adapters.llm.google import GoogleEmbeddings, GoogleStructuredOutput
from app.core.config import Settings
from app.core.credentials import api_key_of, read_credential
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


def environment_credential(provider: ProviderId, settings: Settings) -> SecretStr | None:
    """The credential of a provider as it comes from the environment or `.env`.

    Exposed because a service needs to know whether the key it just stored is
    *also* defined out there, in order to say so instead of resolving the clash
    in silence (art. XI). It hands back the value rather than a boolean so the
    caller can compare, and it is the one function of this module that reads a
    provider-shaped setting on someone else's behalf.
    """
    if provider is ProviderId.GOOGLE:
        return settings.google_api_key
    return None


def environment_credential_name(provider: ProviderId) -> str | None:
    """The variable a user would grep for, so the message can name it.

    Here and not in the service for the usual reason: the name of the variable
    carries the name of the provider (art. XI, ADR-011).
    """
    if provider is ProviderId.GOOGLE:
        return "GOOGLE_API_KEY"
    return None


def credential_for(
    provider: ProviderId, capability: Capability, settings: Settings
) -> SecretStr | None:
    """The credential a call will actually use, with the wizard's one first.

    The inversion of the general precedence lives here and is argued in
    `core/credentials.py`: what the candidate configured on screen is what
    Vokara uses, and the environment is the fallback for whoever prefers files.
    Reading it fresh on every build is what lets a rotation be noticed at all
    (research R-24).
    """
    stored = read_credential(api_key_of(capability), settings)
    if stored is not None:
        return stored
    return environment_credential(provider, settings)


def _google_generation(settings: Settings, credential: SecretStr | None) -> GoogleStructuredOutput:
    return GoogleStructuredOutput(model=settings.google_model, credential=credential)


def _google_embeddings(settings: Settings, credential: SecretStr | None) -> GoogleEmbeddings:
    return GoogleEmbeddings(
        model=settings.google_embed,
        dimensions=settings.embedding_dimensions,
        credential=credential,
    )


def build_structured_output(provider: ProviderId, settings: Settings) -> StructuredOutputPort:
    """The generation port of a provider, with its own credential and model."""
    if provider is not ProviderId.GOOGLE:
        raise ProviderNotImplementedError(provider, Capability.GENERATION)
    return _google_generation(settings, credential_for(provider, Capability.GENERATION, settings))


def build_embeddings(provider: ProviderId, settings: Settings) -> EmbeddingsPort:
    """The embeddings port, configured independently of generation (FR-004)."""
    if provider is not ProviderId.GOOGLE:
        raise ProviderNotImplementedError(provider, Capability.EMBEDDINGS)
    return _google_embeddings(settings, credential_for(provider, Capability.EMBEDDINGS, settings))


def build_probe(
    provider: ProviderId,
    capability: Capability,
    settings: Settings,
    credential: SecretStr | None = None,
) -> CapabilityProbePort:
    """The preflight probe for one capability of one provider (FR-006).

    It returns the same object that will serve the capability afterwards, so
    what gets verified is what gets used: verifying one client and then calling
    a differently configured one would make the preflight a formality.

    `credential` is the key the candidate has just pasted. It is passed
    explicitly rather than read back from configuration so that what the
    preflight measures is that key, unambiguously, on the one call where the two
    could still differ.
    """
    if provider is not ProviderId.GOOGLE:
        raise ProviderNotImplementedError(provider, capability)

    resolved = (
        credential if credential is not None else credential_for(provider, capability, settings)
    )

    match capability:
        case Capability.GENERATION:
            return _google_generation(settings, resolved)
        case Capability.EMBEDDINGS:
            return _google_embeddings(settings, resolved)


def is_implemented(provider: ProviderId) -> bool:
    """Whether an implementation exists, which is not whether it is offerable.

    A row can be verified empirically and still have no code behind it; the
    catalogue comes from `capabilities.py` and this answers the other half.
    """
    return provider is ProviderId.GOOGLE


def implemented_and_offerable(capability: Capability) -> tuple[ProviderId, ...]:
    """What the wizard can actually hand the user for a capability."""
    return tuple(row.provider for row in offerable_for(capability) if is_implemented(row.provider))
