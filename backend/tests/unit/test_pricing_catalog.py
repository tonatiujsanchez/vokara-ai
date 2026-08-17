"""FR-005 as invariants: no option without its cost, no figure without its assumption.

The figures themselves are pending — research R-27 puts the calculation in step
10 of the roadmap, outside this spec. What is tested here is everything that
does not depend on them, which is precisely what makes filling them in a data
edit: that every offerable option has a row, that the two capabilities are
priced apart, and that a number can never reach the screen without the usage
assumption that makes it interpretable.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from app.adapters.llm.capabilities import (
    CAPABILITY_MATRIX,
    ProviderId,
    declares_capability,
    offerable_for,
)
from app.adapters.llm.pricing import (
    PRICING_CATALOGUE,
    CapabilityPricing,
    priced_options,
    pricing_for,
)
from app.domain.capability import Capability


def test_every_offerable_option_has_a_price_beside_it() -> None:
    """FR-005: the cost is shown before the key is asked for, always."""
    for capability in Capability:
        for row in offerable_for(capability):
            assert pricing_for(row.provider, capability) is not None


def test_a_provider_verified_tomorrow_already_has_its_row() -> None:
    """Verifying a provider must not be able to leave an option priceless."""
    for row in CAPABILITY_MATRIX:
        for capability in Capability:
            if declares_capability(row.provider, capability):
                assert pricing_for(row.provider, capability) is not None


def test_nothing_is_priced_for_a_capability_the_provider_does_not_offer() -> None:
    assert pricing_for(ProviderId.ANTHROPIC, Capability.EMBEDDINGS) is None
    assert pricing_for(ProviderId.ANTHROPIC, Capability.GENERATION) is not None


def test_generation_and_embeddings_are_priced_apart() -> None:
    """Summing them would suggest the embeddings provider moves the bill."""
    generation = priced_options(Capability.GENERATION)
    embeddings = priced_options(Capability.EMBEDDINGS)

    assert {row.capability for row in generation} == {Capability.GENERATION}
    assert {row.capability for row in embeddings} == {Capability.EMBEDDINGS}
    assert len(generation) != len(embeddings)


def test_every_option_appears_exactly_once() -> None:
    keys = [(row.provider, row.capability) for row in PRICING_CATALOGUE]
    assert len(keys) == len(set(keys))


@pytest.mark.parametrize(
    "row", PRICING_CATALOGUE, ids=lambda row: f"{row.provider}-{row.capability}"
)
def test_a_figure_never_travels_without_its_usage_assumption(row: CapabilityPricing) -> None:
    """Half a row is worse than none: a number nobody can interpret."""
    if row.estimated_monthly_usd is None:
        assert not row.is_estimated
    else:
        assert row.usage_assumption_es
        assert row.is_estimated


def test_the_suggested_default_is_the_one_with_a_free_tier() -> None:
    """ADR-003: the only one usable for real without a card."""
    row = pricing_for(ProviderId.GOOGLE, Capability.GENERATION)
    assert row is not None
    assert row.has_free_tier is True


def test_an_unmeasured_free_tier_is_declared_unknown_and_not_denied() -> None:
    row = pricing_for(ProviderId.DEEPSEEK, Capability.GENERATION)
    assert row is not None
    assert row.has_free_tier is None


def test_the_catalogue_is_data_and_cannot_be_edited_at_runtime() -> None:
    assert isinstance(PRICING_CATALOGUE, tuple)
    with pytest.raises(FrozenInstanceError):
        PRICING_CATALOGUE[0].estimated_monthly_usd = Decimal("1.00")  # type: ignore[misc]
