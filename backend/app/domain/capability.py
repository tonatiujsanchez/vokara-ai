"""Capabilities and the result of verifying one, as domain types.

Article XI asks features to consult the *capability*, never the provider. That
is only possible if the capability is a type the domain owns, so this module
sits in `domain/` and imports nothing: no adapter, no session, no settings.

The preflight result is a **sum of four variants** and not a boolean because
they are four different situations that deserve four different messages
(FR-007, research R-23). Collapsing `quota_exceeded` into "invalid credential"
sends the candidate to regenerate a key that works perfectly.

`ProviderUnreachable` is deliberately **outside** the sum. Having no connection
says nothing about the credential or the capability: it is a fact about the
environment, it is communicated as «no pudimos verificar» and it lets the user
retry without pasting the key again (research R-23, contracts/errors.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar


class Capability(StrEnum):
    """What Vokara needs from a provider, configured independently (ADR-011)."""

    GENERATION = "generation"
    EMBEDDINGS = "embeddings"

    @property
    def label_es(self) -> str:
        """How the capability is named on screen, in Spanish (art. IX)."""
        match self:
            case Capability.GENERATION:
                return "la salida estructurada"
            case Capability.EMBEDDINGS:
                return "los embeddings"

    @property
    def works_es(self) -> str:
        """«funciona» or «funcionan», to agree with `label_es` in number.

        One of the two labels is plural, so a template that hardcodes the verb
        gets it wrong half the time — «los embeddings funciona». The agreement
        belongs next to the noun that governs it, not in whatever message
        happens to use it: art. IX asks for Spanish, and this is Spanish.
        """
        match self:
            case Capability.GENERATION:
                return "funciona"
            case Capability.EMBEDDINGS:
                return "funcionan"


@dataclass(frozen=True)
class AffectedFeature:
    """A concrete function lost to a degradation, with its stable code (SC-016).

    Concrete, and never a generic warning: «algo podría no funcionar» is not
    informed degradation, it is a shrug. The candidate is being asked to accept
    a loss, so the loss is named before they can accept it (FR-007.3, art. XI).
    """

    code: str
    message_es: str


CV_PARSING = AffectedFeature(
    code="CV_PARSING",
    message_es="Sembrar tu perfil desde el CV puede fallar o traer datos incompletos.",
)

SEMANTIC_MATCHING = AffectedFeature(
    code="SEMANTIC_MATCHING",
    message_es=(
        "El matching semántico quedaría desactivado. El matching por reglas sigue funcionando."
    ),
)


def affected_features(capability: Capability) -> tuple[AffectedFeature, ...]:
    """Which product functions depend on the capability that came back unverified.

    This mapping is domain knowledge and not adapter knowledge: what breaks when
    embeddings are unavailable is a fact about Vokara, not about whoever failed
    to provide them (contracts/errors.md).
    """
    match capability:
        case Capability.GENERATION:
            return (CV_PARSING,)
        case Capability.EMBEDDINGS:
            return (SEMANTIC_MATCHING,)


@dataclass(frozen=True)
class Verified:
    """FR-007.2 — the credential is accepted and the capability holds.

    For embeddings the dimension observed in the probe travels here, because
    that is the value persisted next to every future vector (ADR-003, R-12).
    """

    capability: Capability
    model: str
    embedding_dim: int | None = None

    result: ClassVar[str] = "verified"
    allows_progress: ClassVar[bool] = True


@dataclass(frozen=True)
class CapabilityUnverified:
    """FR-007.3 — valid credential, capability without guarantee.

    Progress is allowed **only** after a specific acknowledgement, and the
    acknowledgement is only honest if the candidate was told two different
    things first: **what** stops working — `affected_features(capability)` — and
    **why** this particular model was not trusted, which is `reasons_es`.

    They are not interchangeable, and the field used to be misnamed
    `affected_features_es`, which is most of the reason nobody noticed it was
    being dropped on the way to the screen. «No podrás sembrar tu perfil desde
    el CV» without «inventó un teléfono que el CV no trae» is half the message:
    the candidate cannot tell an invented value from a malformed answer, and
    those call for different decisions — change the model, or retry.
    """

    capability: Capability
    model: str
    reasons_es: tuple[str, ...] = ()

    result: ClassVar[str] = "capability_unverified"
    allows_progress: ClassVar[bool] = True


@dataclass(frozen=True)
class CredentialRejected:
    """FR-007.1 — invalid, revoked or mis-copied.

    Carries no reason string on purpose: the actionable message lives in the
    error catalogue and the provider's raw text could echo the key back
    (FR-008, contracts/errors.md).
    """

    capability: Capability
    model: str

    result: ClassVar[str] = "credential_rejected"
    allows_progress: ClassVar[bool] = False


@dataclass(frozen=True)
class QuotaExceeded:
    """FR-007.4 — the credential works, the quota does not."""

    capability: Capability
    model: str

    result: ClassVar[str] = "quota_exceeded"
    allows_progress: ClassVar[bool] = False


type PreflightOutcome = Verified | CapabilityUnverified | CredentialRejected | QuotaExceeded


@dataclass(frozen=True)
class ProviderUnreachable:
    """Not a capability result: the provider could not be reached at all.

    Nothing is persisted as a preflight result for this case — a row saying
    "unverified" would be a claim about the provider that was never tested.
    """

    capability: Capability
    model: str

    allows_progress: ClassVar[bool] = False


type PreflightAttempt = PreflightOutcome | ProviderUnreachable
