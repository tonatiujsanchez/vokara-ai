"""The pending step of the first run, derived from facts (research R-18, FR-014).

There is no "current step" column anywhere, and that absence is the design. A
persisted pointer desynchronises from reality the moment anything happens
outside the expected flow — the user rotates an API key in their configuration,
a preflight is invalidated, they come back two weeks later — and every one of
those cases would need code to repair the pointer. Derived from the facts that
*are* persisted (the acknowledgement with its version, the preflight of each
capability, the state of the email step), the step is self-repairing and always
correct.

Four branches, in wizard order:

```
sin acuse vigente                                    → disclosure
generación no utilizable                             → providers
embeddings no utilizable y correo pendiente          → providers
correo pendiente                                     → email
resto                                                → null
```

**Why the embeddings branch carries `y correo pendiente`.** Embeddings is not a
mandatory step: FR-010 is explicit that its absence never blocks the onboarding,
it degrades the features that depend on vectors and says so. So while the wizard
is still running — which is exactly what «correo pendiente» means, since email is
the last step — an unresolved embeddings sends the user back to finish it; once
the first run has concluded, it never reopens it. Without that qualifier a
candidate who chose not to configure embeddings, or whose key was rejected,
would be sent to `providers` forever and could never reach the onboarding, which
is the blocking FR-010 forbids.

The qualifier also buys an equivalence worth keeping: `pending_step is None` iff
`is_complete`, which is what the HTTP contract promises («`null` ⇔ la primera
ejecución concluyó»). The embeddings branch can only fire while the email step
is pending, and that already forces a non-null step.

This module imports nothing outside `domain/`: these are pure rules and they are
tested as such (art. II).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.domain.capability import Capability, CapabilityUnverified, Verified


class SetupStep(StrEnum):
    """The step the wizard resumes at. Derived, never stored."""

    DISCLOSURE = "disclosure"
    PROVIDERS = "providers"
    EMAIL = "email"


class EmailStepStatus(StrEnum):
    """The optional step: pending until the candidate links **or** skips it."""

    PENDING = "pending"
    LINKED = "linked"
    SKIPPED = "skipped"


# The two preflight results that leave a capability usable (FR-007.2, FR-007.3).
# Read off the variants instead of repeated as literals, so adding a fifth
# result cannot silently keep this rule describing the old four.
USABLE_RESULTS: frozenset[str] = frozenset({Verified.result, CapabilityUnverified.result})


@dataclass(frozen=True)
class ProviderFacts:
    """What was recorded about one capability, plus whether its key still matches.

    `credential_matches` is the answer to research R-24: the credential lives in
    local configuration and the preflight result lives in the database, so they
    can diverge. A stored «verificada» about a key the user has since replaced is
    a result that lies, and the honest reading of it is «not usable».
    """

    capability: Capability
    result: str
    credential_matches: bool = True
    degradation_acknowledged: bool = False

    @property
    def is_usable(self) -> bool:
        """`verified`, or `capability_unverified` **with** its acknowledgement.

        The acknowledgement is what art. XI demands in exchange for continuing
        with a capability nobody could guarantee: the affected features were
        enumerated first and the candidate said yes to them (FR-007.3, SC-016).
        """
        if not self.credential_matches:
            return False
        if self.result == CapabilityUnverified.result:
            return self.degradation_acknowledged
        return self.result == Verified.result


@dataclass(frozen=True)
class SetupFacts:
    """Everything the derivation reads. No pointer among them (research R-18)."""

    current_disclosure_version: str
    acknowledged_disclosure_version: str | None
    generation: ProviderFacts | None
    embeddings: ProviderFacts | None
    email_status: EmailStepStatus

    @property
    def disclosure_acknowledged(self) -> bool:
        """An acknowledgement of an older text does not cover the current one.

        Storing *which* version was accepted is what makes this comparison
        possible, and it is the whole reason the text is versioned: a change in
        what Vokara sends to the provider must be able to demand a new
        acknowledgement instead of being covered by an old one that said
        something else (research R-29, FR-048).
        """
        return (
            self.acknowledged_disclosure_version is not None
            and self.acknowledged_disclosure_version == self.current_disclosure_version
        )


def _is_usable(provider: ProviderFacts | None) -> bool:
    return provider is not None and provider.is_usable


def pending_step(facts: SetupFacts) -> SetupStep | None:
    """Where the wizard resumes, or `None` when the first run has concluded."""
    if not facts.disclosure_acknowledged:
        return SetupStep.DISCLOSURE

    if not _is_usable(facts.generation):
        return SetupStep.PROVIDERS

    if facts.email_status is EmailStepStatus.PENDING:
        # Still inside the wizard: finish the optional capability before
        # offering the optional step. Afterwards it never reopens (FR-010).
        if not _is_usable(facts.embeddings):
            return SetupStep.PROVIDERS
        return SetupStep.EMAIL

    return None


def is_complete(facts: SetupFacts) -> bool:
    """FR-015: acknowledgement, generation usable, email finished or skipped.

    Embeddings is deliberately absent from this rule. It is the capability whose
    absence degrades explicitly instead of blocking, so making it a condition of
    concluding the first run would be the blocking FR-010 forbids.
    """
    return (
        facts.disclosure_acknowledged
        and _is_usable(facts.generation)
        and facts.email_status is not EmailStepStatus.PENDING
    )
