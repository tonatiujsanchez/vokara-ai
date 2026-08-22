"""The four variants are four, they are exhaustive, and they stay distinguishable.

What is being protected here is FR-007: four preflight situations that must
reach the candidate as four different messages. A future variant added without
handling it everywhere, or a variant quietly dropped, breaks these tests before
it reaches a user (research R-23).
"""

from __future__ import annotations

import typing
from typing import assert_never, get_args

import pytest

from app.domain.capability import (
    Capability,
    CapabilityUnverified,
    CredentialRejected,
    PreflightAttempt,
    PreflightOutcome,
    ProviderUnreachable,
    QuotaExceeded,
    Verified,
)

MODEL = "a-configured-model"


def _variants(alias: typing.TypeAliasType) -> tuple[type, ...]:
    variants: tuple[type, ...] = get_args(alias.__value__)
    return variants


def describe(outcome: PreflightOutcome) -> str:
    """Exhaustive dispatch: mypy --strict fails if a variant is left unhandled.

    This is the shape every interpreter of the outcome has to take, and the
    reason the sum type earns its keep over a status string.
    """
    match outcome:
        case Verified():
            return "verified"
        case CapabilityUnverified():
            return "capability_unverified"
        case CredentialRejected():
            return "credential_rejected"
        case QuotaExceeded():
            return "quota_exceeded"
        case _:  # pragma: no cover — unreachable while the sum has four members
            assert_never(outcome)


def test_the_sum_has_exactly_four_variants() -> None:
    assert _variants(PreflightOutcome) == (
        Verified,
        CapabilityUnverified,
        CredentialRejected,
        QuotaExceeded,
    )


def test_provider_unreachable_is_not_a_preflight_outcome() -> None:
    """Having no connection is a fact about the environment, not about the key."""
    assert ProviderUnreachable not in _variants(PreflightOutcome)
    assert ProviderUnreachable in _variants(PreflightAttempt)


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (Verified(capability=Capability.GENERATION, model=MODEL), "verified"),
        (
            CapabilityUnverified(capability=Capability.GENERATION, model=MODEL),
            "capability_unverified",
        ),
        (CredentialRejected(capability=Capability.GENERATION, model=MODEL), "credential_rejected"),
        (QuotaExceeded(capability=Capability.GENERATION, model=MODEL), "quota_exceeded"),
    ],
)
def test_every_variant_dispatches_to_its_own_branch(
    outcome: PreflightOutcome, expected: str
) -> None:
    assert describe(outcome) == expected


def test_every_variant_carries_the_code_that_gets_persisted() -> None:
    """The four values of the `preflight_result` enum in the database, no more."""
    codes = {variant.result for variant in _variants(PreflightOutcome)}  # type: ignore[attr-defined]
    assert codes == {"verified", "capability_unverified", "credential_rejected", "quota_exceeded"}


@pytest.mark.parametrize(
    ("outcome", "allows_progress"),
    [
        (Verified(capability=Capability.GENERATION, model=MODEL), True),
        (CapabilityUnverified(capability=Capability.GENERATION, model=MODEL), True),
        (CredentialRejected(capability=Capability.GENERATION, model=MODEL), False),
        (QuotaExceeded(capability=Capability.GENERATION, model=MODEL), False),
        (ProviderUnreachable(capability=Capability.GENERATION, model=MODEL), False),
    ],
)
def test_only_verified_and_unverified_let_the_wizard_move_on(
    outcome: PreflightAttempt, allows_progress: bool
) -> None:
    """FR-010: the gate accepts result 2 or 3 of FR-007, and nothing else."""
    assert outcome.allows_progress is allows_progress


def test_the_dimension_only_travels_with_a_verified_embeddings_probe() -> None:
    probe = Verified(capability=Capability.EMBEDDINGS, model=MODEL, embedding_dim=768)
    assert probe.embedding_dim == 768
    assert Verified(capability=Capability.GENERATION, model=MODEL).embedding_dim is None


def test_an_outcome_cannot_be_edited_after_the_fact() -> None:
    outcome = Verified(capability=Capability.GENERATION, model=MODEL)
    with pytest.raises(AttributeError):
        outcome.model = "another-model"  # type: ignore[misc]


def test_the_degradation_enumerates_what_stops_working_before_it_is_acknowledged() -> None:
    """FR-007.3: the acknowledgement is only honest if the loss was listed first."""
    unverified = CapabilityUnverified(
        capability=Capability.EMBEDDINGS,
        model=MODEL,
        reasons_es=("Búsqueda semántica de vacantes",),
    )
    assert unverified.reasons_es == ("Búsqueda semántica de vacantes",)
