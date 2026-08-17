"""The preflight: run when the key is saved, never deferred (FR-006, R-23).

This module is the **single interpreter of the four results**. The adapter
classifies what the provider did — only it knows what a 401 or a 429 looks like
there — and hands back a typed variant; everything downstream reads the variant,
never a raw error (art. II, research R-23).

Three properties are worth stating because they are what the requirement is
made of:

- **It runs at save time.** Deferring it to the first real parse would turn the
  first use of the product into the moment of discovering the provider has to be
  reconfigured, which is exactly what FR-006 forbids and what art. XI calls a
  fallo opaco.
- **Four results, four consequences.** `verified` and `capability_unverified`
  leave the capability usable — the second one only after its specific
  acknowledgement — while `credential_rejected` and `quota_exceeded` do not.
  `provider_unreachable` is not a result about the capability at all and
  persists nothing: a stored «sin verificar» would be a claim about a provider
  nobody managed to ask.
- **The credential is written before it is probed.** That is what lets a
  preflight that could not reach the provider be retried without pasting the key
  again, which the spec asks for by name.

**The fingerprint** (research R-24). The key lives in local configuration and
the result lives in the database; two places that can diverge the moment someone
edits a file. So each row stores an HMAC-SHA256 of the credential, keyed with a
per-installation secret and truncated — not the key and not a fragment of it,
which is what FR-008 forbids — and every read compares it against the credential
in force. A mismatch invalidates that capability, and only that one.
"""

from __future__ import annotations

import asyncio
import hmac
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Protocol
from uuid import UUID

from pydantic import SecretStr

from app.adapters.llm.base import CapabilityProbePort, ProviderCallError, ProviderFailure
from app.adapters.llm.capabilities import ProviderId
from app.adapters.llm.directory import console_url_of
from app.adapters.llm.factory import (
    build_probe,
    credential_for,
    default_model,
    environment_credential,
    environment_credential_name,
    implemented_and_offerable,
)
from app.core.config import Settings, get_settings
from app.core.credentials import api_key_of, installation_key, write_credential
from app.core.logging import get_logger
from app.db.repositories.provider_configuration_repository import (
    ProviderConfigurationRepository,
)
from app.db.session import session_scope
from app.domain.capability import (
    AffectedFeature,
    Capability,
    CapabilityUnverified,
    CredentialRejected,
    PreflightAttempt,
    ProviderUnreachable,
    QuotaExceeded,
    Verified,
    affected_features,
)
from app.domain.errors import (
    DegradationAcknowledgementRequiredError,
    ModelNotAvailableError,
    ProviderCredentialRejectedError,
    ProviderNotOfferedError,
    ProviderQuotaExceededError,
    ProviderUnreachableError,
)
from app.domain.setup import CredentialStatus, ProviderFacts

logger = get_logger(__name__)

# Half of a SHA-256 is 128 bits of digest: far more than enough to notice that a
# credential changed, and short enough to make clear it is not storage.
FINGERPRINT_CHARS = 32

_VERIFIED_MESSAGE = "Tu API key quedó verificada: {capability} funciona con este modelo."
_UNVERIFIED_MESSAGE = (
    "Tu API key funciona, pero este modelo no garantiza {capability}. "
    "Esto es lo que no podrás hacer:"
)
_SHADOWED_MESSAGE = (
    "Esta credencial también está definida en tu configuración de entorno ({variable}); "
    "Vokara usará la que acabas de configurar aquí."
)
_SHADOWED_MESSAGE_UNNAMED = (
    "Esta credencial también está definida en tu configuración de entorno; "
    "Vokara usará la que acabas de configurar aquí."
)


@dataclass(frozen=True)
class PreflightView:
    """One preflight result as the contract exposes it. Never a key, never a trace."""

    result: str
    checked_at: datetime
    message_es: str
    embedding_dim: int | None = None
    affected: tuple[AffectedFeature, ...] = ()


@dataclass(frozen=True)
class ProviderConfigurationView:
    """The configuration of one capability, with nothing secret in it (FR-008)."""

    capability: Capability
    provider: str
    model: str
    credential_status: CredentialStatus
    preflight: PreflightView
    degradation_acknowledged_at: datetime | None
    is_usable: bool
    configuration_notice_es: str | None = None

    def as_facts(self) -> ProviderFacts:
        """What the derivation of the pending step reads (research R-18)."""
        return ProviderFacts(
            capability=self.capability,
            result=self.preflight.result,
            credential_matches=self.credential_status is not CredentialStatus.NOT_CONFIGURED,
            degradation_acknowledged=self.degradation_acknowledged_at is not None,
        )


def fingerprint(credential: SecretStr, settings: Settings | None = None) -> str:
    """A digest of the credential, useless outside this installation (R-24).

    Keyed with the installation secret precisely so it cannot be recomputed
    elsewhere: an unkeyed digest of a short API key would be a lookup away from
    the key itself, and FR-008 forbids storing even a part of it.
    """
    resolved = settings or get_settings()
    digest = hmac.new(
        installation_key(resolved), credential.get_secret_value().encode("utf-8"), sha256
    )
    return digest.hexdigest()[:FINGERPRINT_CHARS]


def _resolve_offerable(provider: str, capability: Capability) -> ProviderId:
    """FR-009: what is not verified and implemented is not configurable."""
    try:
        candidate = ProviderId(provider)
    except ValueError:
        raise ProviderNotOfferedError from None

    if candidate not in implemented_and_offerable(capability):
        raise ProviderNotOfferedError

    return candidate


def _shadow_notice(provider: ProviderId, settings: Settings) -> str | None:
    """Say it out loud when the same credential also lives in the environment.

    The wizard's file wins — see `core/credentials.py` — and the one thing a
    system may not do with a resolution like that is apply it in silence: the
    candidate would have two keys and no way of knowing which one is in use
    (art. XI, art. X).
    """
    if environment_credential(provider, settings) is None:
        return None

    variable = environment_credential_name(provider)
    if variable is None:
        return _SHADOWED_MESSAGE_UNNAMED
    return _SHADOWED_MESSAGE.format(variable=variable)


def _probe_now(probe: CapabilityProbePort, model: str) -> PreflightAttempt:
    """Run the probe, translating the one failure that is not a result.

    A retired model says nothing about the credential or the capability: it is a
    configuration problem with its own actionable message, so it keeps
    travelling as an error instead of being flattened into «no verificada»
    (ADR-011, contracts/errors.md).
    """
    try:
        return asyncio.run(probe.probe())
    except ProviderCallError as error:
        if error.failure is ProviderFailure.MODEL_NOT_AVAILABLE:
            raise ModelNotAvailableError(configured_model=model) from None
        raise


class ProbeFactory(Protocol):
    """How a probe is obtained. The seam exists so tests do not call a provider.

    Production passes `build_probe`, which is the factory of art. XI: the one
    module that turns an identifier into an implementation. A test passes a
    double and gets to drive the four results without a network, which is the
    only way SC-012 and SC-016 can be verified at all.
    """

    def __call__(
        self,
        provider: ProviderId,
        capability: Capability,
        settings: Settings,
        credential: SecretStr | None = None,
        model: str | None = None,
    ) -> CapabilityProbePort: ...


def configure_capability(
    candidate_id: UUID,
    capability: Capability,
    *,
    provider: str,
    api_key: SecretStr,
    model: str | None = None,
    settings: Settings | None = None,
    probe_factory: ProbeFactory = build_probe,
) -> ProviderConfigurationView:
    """Store the credential, probe the capability with it, record what happened.

    Raises the catalogue's error for the results that do not allow progress. They
    are not transport failures — the request worked perfectly — but the contract
    answers them as errors so the frontend can branch on a code instead of
    inspecting a body (contracts/openapi.yaml, PUT /setup/providers).
    """
    resolved = settings or get_settings()
    chosen = _resolve_offerable(provider, capability)
    model_name = model or default_model(chosen, capability, resolved)

    # Written before the probe: a preflight that cannot reach the provider must
    # be retriable without asking for the key again (edge case of the spec).
    write_credential(api_key_of(capability), api_key, resolved)

    probe = probe_factory(chosen, capability, resolved, credential=api_key, model=model_name)
    attempt = _probe_now(probe, model_name)
    digest = fingerprint(api_key, resolved)

    logger.info(
        "preflight_completed",
        capability=capability.value,
        provider=chosen.value,
        model=model_name,
        # The classification, never the key and never the provider's text.
        result=getattr(attempt, "result", "provider_unreachable"),
    )

    if isinstance(attempt, ProviderUnreachable):
        # Nothing is persisted: a row saying «unverified» would be a claim about
        # a provider nobody managed to ask (domain/capability.py).
        raise ProviderUnreachableError

    with session_scope() as session:
        row = ProviderConfigurationRepository(session).save_preflight(
            candidate_id,
            capability=capability,
            provider=chosen.value,
            model=model_name,
            result=attempt.result,
            credential_fingerprint=digest,
            embedding_dim=getattr(attempt, "embedding_dim", None),
        )
        view = _view_of(
            capability=capability,
            provider=row.provider,
            model=row.model,
            result=row.preflight_result,
            checked_at=row.preflight_at,
            embedding_dim=row.embedding_dim,
            degradation_acknowledged_at=row.degradation_acknowledged_at,
            credential_matches=True,
            notice=_shadow_notice(chosen, resolved),
        )

    match attempt:
        case CredentialRejected():
            raise ProviderCredentialRejectedError(console_url=console_url_of(chosen.value))
        case QuotaExceeded():
            raise ProviderQuotaExceededError
        case _:
            return view


def current_configuration(
    candidate_id: UUID, capability: Capability, settings: Settings | None = None
) -> ProviderConfigurationView | None:
    """The stored configuration, re-checked against the credential in force.

    The re-check is the whole of research R-24: if the candidate rotated the key
    outside the application, the persisted «verificada» describes a credential
    that is no longer there, and repeating it would be a result that lies.
    """
    resolved = settings or get_settings()

    with session_scope() as session:
        row = ProviderConfigurationRepository(session).for_capability(candidate_id, capability)
        if row is None:
            return None

        stored = (
            row.provider,
            row.model,
            row.preflight_result,
            row.preflight_at,
            row.embedding_dim,
            row.degradation_acknowledged_at,
            row.credential_fingerprint,
        )

    provider, model, result, checked_at, dim, acknowledged_at, digest = stored
    return _view_of(
        capability=capability,
        provider=provider,
        model=model,
        result=result,
        checked_at=checked_at,
        embedding_dim=dim,
        degradation_acknowledged_at=acknowledged_at,
        credential_matches=_credential_still_matches(provider, capability, digest, resolved),
    )


def acknowledge_degradation(
    candidate_id: UUID, capability: Capability, settings: Settings | None = None
) -> ProviderConfigurationView:
    """Record the acknowledgement FR-007.3 demands, and only where it applies.

    On any other result there is no degradation to acknowledge, and answering
    409 rather than accepting the acknowledgement keeps the record honest: the
    database refuses it too.
    """
    resolved = settings or get_settings()
    existing = current_configuration(candidate_id, capability, resolved)

    if existing is None or existing.preflight.result != CapabilityUnverified.result:
        raise DegradationAcknowledgementRequiredError(
            affected_features=[
                {"code": feature.code, "message": feature.message_es}
                for feature in affected_features(capability)
            ]
        )

    with session_scope() as session:
        ProviderConfigurationRepository(session).acknowledge_degradation(candidate_id, capability)

    acknowledged = current_configuration(candidate_id, capability, resolved)
    if acknowledged is None:  # pragma: no cover — the row was just read and updated
        raise DegradationAcknowledgementRequiredError
    return acknowledged


def usable_generation(candidate_id: UUID, settings: Settings | None = None) -> bool:
    """The gate of FR-010, asked as one question so callers cannot get it wrong."""
    configuration = current_configuration(candidate_id, Capability.GENERATION, settings)
    return configuration is not None and configuration.is_usable


def _credential_still_matches(
    provider: str, capability: Capability, digest: str, settings: Settings
) -> bool:
    try:
        known = ProviderId(provider)
    except ValueError:  # pragma: no cover — the closed list is validated on the way in
        return False

    credential = credential_for(known, capability, settings)
    if credential is None:
        return False
    return hmac.compare_digest(fingerprint(credential, settings), digest)


def _view_of(
    *,
    capability: Capability,
    provider: str,
    model: str,
    result: str,
    checked_at: datetime,
    embedding_dim: int | None,
    degradation_acknowledged_at: datetime | None,
    credential_matches: bool,
    notice: str | None = None,
) -> ProviderConfigurationView:
    facts = ProviderFacts(
        capability=capability,
        result=result,
        credential_matches=credential_matches,
        degradation_acknowledged=degradation_acknowledged_at is not None,
    )

    return ProviderConfigurationView(
        capability=capability,
        provider=provider,
        model=model,
        credential_status=_credential_status(result, credential_matches=credential_matches),
        preflight=PreflightView(
            result=result,
            checked_at=checked_at,
            message_es=_message_for_result(result, capability),
            embedding_dim=embedding_dim,
            affected=affected_features(capability) if result == CapabilityUnverified.result else (),
        ),
        degradation_acknowledged_at=degradation_acknowledged_at,
        is_usable=facts.is_usable,
        configuration_notice_es=notice,
    )


def _credential_status(result: str, *, credential_matches: bool) -> CredentialStatus:
    """Configured, not configured, or rejected. There is no fourth answer (FR-008).

    A credential that no longer matches its fingerprint reads as *not
    configured* rather than as rejected: nobody rejected it, it is simply not
    the one that was verified, and the honest thing to ask for is a new
    preflight (research R-24).
    """
    if not credential_matches:
        return CredentialStatus.NOT_CONFIGURED
    if result == CredentialRejected.result:
        return CredentialStatus.REJECTED
    return CredentialStatus.CONFIGURED


def _message_for_result(result: str, capability: Capability) -> str:
    match result:
        case Verified.result:
            return _VERIFIED_MESSAGE.format(capability=capability.label_es)
        case CapabilityUnverified.result:
            return _UNVERIFIED_MESSAGE.format(capability=capability.label_es)
        case CredentialRejected.result:
            return ProviderCredentialRejectedError.message
        case _:
            return ProviderQuotaExceededError.message
