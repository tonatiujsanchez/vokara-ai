"""The four branches of the derived step, and the equivalence it must keep.

The rules are pure, so they are tested pure: no database, no HTTP, no adapter.
That is the point of deriving the step instead of storing it (research R-18).
"""

from __future__ import annotations

import pytest

from app.domain.capability import (
    Capability,
    CapabilityUnverified,
    CredentialRejected,
    QuotaExceeded,
    Verified,
)
from app.domain.setup import (
    EmailStepStatus,
    ProviderFacts,
    SetupFacts,
    SetupStep,
    is_complete,
    pending_step,
)

CURRENT_VERSION = "2026-08-11"


def facts(
    *,
    acknowledged: str | None = CURRENT_VERSION,
    generation: ProviderFacts | None = None,
    embeddings: ProviderFacts | None = None,
    email_status: EmailStepStatus = EmailStepStatus.PENDING,
) -> SetupFacts:
    return SetupFacts(
        current_disclosure_version=CURRENT_VERSION,
        acknowledged_disclosure_version=acknowledged,
        generation=generation,
        embeddings=embeddings,
        email_status=email_status,
    )


def resolved(
    capability: Capability,
    result: str = Verified.result,
    *,
    credential_matches: bool = True,
    degradation_acknowledged: bool = False,
) -> ProviderFacts:
    return ProviderFacts(
        capability=capability,
        result=result,
        credential_matches=credential_matches,
        degradation_acknowledged=degradation_acknowledged,
    )


GENERATION_VERIFIED = resolved(Capability.GENERATION)
EMBEDDINGS_VERIFIED = resolved(Capability.EMBEDDINGS)


# ── branch 1: disclosure ────────────────────────────────────────────────────


def test_without_any_acknowledgement_the_step_is_the_disclosure() -> None:
    assert pending_step(facts(acknowledged=None)) is SetupStep.DISCLOSURE


def test_an_acknowledgement_of_an_older_text_does_not_cover_the_current_one() -> None:
    """Versioning the text is pointless if an old yes covers a new text (R-29)."""
    stale = facts(
        acknowledged="2026-01-01",
        generation=GENERATION_VERIFIED,
        embeddings=EMBEDDINGS_VERIFIED,
    )

    assert pending_step(stale) is SetupStep.DISCLOSURE


def test_the_disclosure_wins_over_everything_else_that_is_pending() -> None:
    """It is step zero: art. V puts it before any field to fill in."""
    assert pending_step(facts(acknowledged=None, email_status=EmailStepStatus.SKIPPED)) is (
        SetupStep.DISCLOSURE
    )


# ── branch 2: providers, because of generation ──────────────────────────────


def test_with_the_acknowledgement_but_no_generation_the_step_is_providers() -> None:
    assert pending_step(facts()) is SetupStep.PROVIDERS


@pytest.mark.parametrize("result", [CredentialRejected.result, QuotaExceeded.result])
def test_a_generation_that_did_not_pass_its_preflight_keeps_the_step_at_providers(
    result: str,
) -> None:
    """Rejected and quota-exceeded are different messages, same consequence."""
    unusable = facts(generation=resolved(Capability.GENERATION, result))

    assert pending_step(unusable) is SetupStep.PROVIDERS


def test_a_degraded_generation_without_its_acknowledgement_is_not_usable() -> None:
    """Silent degradation is what art. XI forbids; the ack is the price of it."""
    degraded = facts(generation=resolved(Capability.GENERATION, CapabilityUnverified.result))

    assert pending_step(degraded) is SetupStep.PROVIDERS


def test_a_degraded_generation_with_its_acknowledgement_moves_on() -> None:
    acknowledged = facts(
        generation=resolved(
            Capability.GENERATION,
            CapabilityUnverified.result,
            degradation_acknowledged=True,
        ),
        embeddings=resolved(Capability.EMBEDDINGS),
    )

    assert pending_step(acknowledged) is SetupStep.EMAIL


def test_a_rotated_generation_credential_sends_the_wizard_back_to_providers() -> None:
    """A stored «verificada» about a key that changed is a result that lies (R-24)."""
    rotated = facts(
        generation=resolved(Capability.GENERATION, credential_matches=False),
        embeddings=resolved(Capability.EMBEDDINGS),
        email_status=EmailStepStatus.SKIPPED,
    )

    assert pending_step(rotated) is SetupStep.PROVIDERS


# ── branch 3: providers, because of embeddings, while the wizard runs ───────


def test_with_only_generation_verified_the_wizard_resumes_at_providers() -> None:
    """US1 AC12 and SC-015: it resumes at embeddings, not at the acknowledgement."""
    halfway = facts(generation=resolved(Capability.GENERATION))

    assert pending_step(halfway) is SetupStep.PROVIDERS
    assert halfway.disclosure_acknowledged is True


def test_embeddings_stops_holding_the_step_once_the_first_run_concluded() -> None:
    """FR-010: its absence degrades explicitly, it never blocks the onboarding."""
    concluded = facts(
        generation=resolved(Capability.GENERATION),
        email_status=EmailStepStatus.SKIPPED,
    )

    assert pending_step(concluded) is None


def test_a_rotated_embeddings_credential_does_not_reopen_a_concluded_first_run() -> None:
    """Same reason: no path back into the wizard may lock the onboarding out."""
    rotated = facts(
        generation=resolved(Capability.GENERATION),
        embeddings=resolved(Capability.EMBEDDINGS, credential_matches=False),
        email_status=EmailStepStatus.LINKED,
    )

    assert pending_step(rotated) is None


# ── branch 4: email, and the end ────────────────────────────────────────────


def test_with_both_capabilities_usable_the_step_is_the_optional_email() -> None:
    assert (
        pending_step(facts(generation=GENERATION_VERIFIED, embeddings=EMBEDDINGS_VERIFIED))
        is SetupStep.EMAIL
    )


@pytest.mark.parametrize("status", [EmailStepStatus.LINKED, EmailStepStatus.SKIPPED])
def test_linking_and_skipping_end_the_first_run_alike(status: EmailStepStatus) -> None:
    """Skipping is a valid ending, not a lesser one (FR-011)."""
    finished = facts(
        generation=GENERATION_VERIFIED,
        embeddings=EMBEDDINGS_VERIFIED,
        email_status=status,
    )

    assert pending_step(finished) is None
    assert is_complete(finished) is True


# ── the equivalence the HTTP contract promises ──────────────────────────────


@pytest.mark.parametrize("acknowledged", [None, "2026-01-01", CURRENT_VERSION])
@pytest.mark.parametrize(
    "generation",
    [None, Verified.result, CredentialRejected.result, CapabilityUnverified.result],
)
@pytest.mark.parametrize("embeddings", [None, Verified.result, QuotaExceeded.result])
@pytest.mark.parametrize("email_status", list(EmailStepStatus))
def test_no_pending_step_means_exactly_a_concluded_first_run(
    acknowledged: str | None,
    generation: str | None,
    embeddings: str | None,
    email_status: EmailStepStatus,
) -> None:
    """`null` ⇔ concluida, over every combination of facts that can exist.

    The contract states the equivalence and the frontend guard depends on it: a
    combination where the step is `null` but the run is not complete would let
    someone reach the onboarding without a provider (FR-010, FR-015).
    """
    combination = facts(
        acknowledged=acknowledged,
        generation=(
            None
            if generation is None
            else resolved(Capability.GENERATION, generation, degradation_acknowledged=True)
        ),
        embeddings=(
            None
            if embeddings is None
            else resolved(Capability.EMBEDDINGS, embeddings, degradation_acknowledged=True)
        ),
        email_status=email_status,
    )

    assert (pending_step(combination) is None) == is_complete(combination)


def test_every_step_of_the_enum_is_reachable() -> None:
    """A branch nobody can reach is a branch that is not really there."""
    reached = {
        pending_step(facts(acknowledged=None)),
        pending_step(facts()),
        pending_step(facts(generation=GENERATION_VERIFIED, embeddings=EMBEDDINGS_VERIFIED)),
        pending_step(
            facts(
                generation=GENERATION_VERIFIED,
                embeddings=EMBEDDINGS_VERIFIED,
                email_status=EmailStepStatus.SKIPPED,
            )
        ),
    }

    assert reached == {*SetupStep, None}
