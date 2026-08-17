"""The catalogue: only what was verified, priced separately, ready to render.

The test never names a provider. That is not a stylistic choice — it is the same
rule the frontend follows (art. XI): what is asserted is that the catalogue is
built from the verified rows of the matrix, not that a particular company is in
it. When a second provider is verified, this test keeps passing without an edit,
which is exactly the property that says the code is not tied to the first one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings
from app.domain.capability import Capability
from app.services.provider_catalog_service import catalogue, options_for


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path)


def test_both_capabilities_are_separate_lists(settings: Settings) -> None:
    """They are two independent choices, so they are two answers (ADR-011)."""
    result = catalogue(settings)

    assert result.generation == options_for(Capability.GENERATION, settings)
    assert result.embeddings == options_for(Capability.EMBEDDINGS, settings)


def test_the_screen_gets_the_reason_the_two_are_separate(settings: Settings) -> None:
    """One line, on the screen, so the split does not read as a complication."""
    assert "embeddings" in catalogue(settings).separation_reason_es
    assert "matching semántico" in catalogue(settings).separation_reason_es


@pytest.mark.parametrize("capability", list(Capability))
def test_every_option_is_verified_implemented_and_complete(
    capability: Capability, settings: Settings
) -> None:
    """FR-009: what has no empirical verification on record is not offered."""
    from app.adapters.llm.capabilities import ProviderId as Closed
    from app.adapters.llm.capabilities import capabilities_of

    for option in options_for(capability, settings):
        row = capabilities_of(Closed(option.provider))
        assert row.verified_on is not None
        assert option.display_name
        assert option.credential_url.startswith("https://")
        assert option.default_model


def test_the_catalogue_is_not_empty(settings: Settings) -> None:
    """An empty wizard would be a dead end, and the matrix has a verified row."""
    assert options_for(Capability.GENERATION, settings)
    assert options_for(Capability.EMBEDDINGS, settings)


def test_exactly_one_option_is_the_suggested_default(settings: Settings) -> None:
    """Preselected so the common case is one click; the rest are shown as equals."""
    for capability in Capability:
        suggested = [
            option for option in options_for(capability, settings) if option.is_suggested_default
        ]
        assert len(suggested) == 1


def test_only_the_embeddings_options_carry_a_dimension(settings: Settings) -> None:
    """The dimension is what gets persisted beside every vector (ADR-003)."""
    for option in options_for(Capability.EMBEDDINGS, settings):
        assert option.embedding_dim is not None
    for option in options_for(Capability.GENERATION, settings):
        assert option.embedding_dim is None


def test_the_default_model_comes_from_configuration(tmp_path: Path) -> None:
    """Never a constant in code: a retired model must be fixable by the user."""
    configured = Settings(data_dir=tmp_path, google_model="un-modelo-de-mi-configuracion")

    models = {option.default_model for option in options_for(Capability.GENERATION, configured)}

    assert "un-modelo-de-mi-configuracion" in models


def test_a_pending_estimate_says_so_instead_of_inventing_a_figure(settings: Settings) -> None:
    """Art. IV applied to what Vokara says about itself (research R-27)."""
    for capability in Capability:
        for option in options_for(capability, settings):
            cost = option.estimated_cost
            if cost.is_estimated:
                assert cost.amount_usd is not None
                assert cost.usage_assumption_es
            else:
                assert cost.amount_usd is None
                assert cost.pending_note_es


def test_the_cost_is_estimated_per_capability_and_never_added_up(settings: Settings) -> None:
    """Summing them would suggest the embeddings provider moves the bill."""
    generation = options_for(Capability.GENERATION, settings)[0]
    embeddings = options_for(Capability.EMBEDDINGS, settings)[0]

    assert generation.estimated_cost is not embeddings.estimated_cost
    assert generation.estimated_cost.currency == "USD"


def test_the_free_tier_of_an_option_that_has_one_is_declared(settings: Settings) -> None:
    """It is the reason the suggested default is suggested at all (ADR-003)."""
    suggested = [
        option
        for option in options_for(Capability.GENERATION, settings)
        if option.is_suggested_default
    ]

    assert suggested[0].estimated_cost.has_free_tier is True
