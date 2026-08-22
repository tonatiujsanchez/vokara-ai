"""The capability matrix is data, and this is what keeps it honest.

ADR-011 says it plainly: «la matriz declarada en el código no vale más que la
verificación que la respalda». So `verified_on` is a date and not a boolean —
an old date is a reason to test again — and a row without one never reaches the
catalogue the API offers (FR-009).

Written before `capabilities.py` existed, as tasks.md rule 1 requires: the
suite recorded eight `xfail(strict=True)` runs against a module that did not
exist yet, and T042 removed the mark in the same step. The imports stay inside
each test, which is what made the absence show up as a failure the xfail could
record instead of a collection error that hides it.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from app.domain.capability import Capability

# The closed list of ADR-011. Five, and the four unverified ones are not a
# to-do list: they are declared so the matrix says what is *not* offered too.
EXPECTED_PROVIDERS = frozenset({"google", "openai", "anthropic", "deepseek", "moonshot"})


def test_the_matrix_declares_the_five_rows_of_the_closed_list() -> None:
    from app.adapters.llm.capabilities import CAPABILITY_MATRIX

    assert len(CAPABILITY_MATRIX) == 5
    assert {row.provider.value for row in CAPABILITY_MATRIX} == EXPECTED_PROVIDERS


def test_only_a_row_with_a_verification_date_is_ever_offered() -> None:
    """FR-009: what has not been verified empirically is not announced."""
    from app.adapters.llm.capabilities import CAPABILITY_MATRIX, offerable_for

    offered = {row.provider for capability in Capability for row in offerable_for(capability)}
    unverified = {row.provider for row in CAPABILITY_MATRIX if row.verified_on is None}

    assert offered
    assert not offered & unverified


def test_generation_and_embeddings_are_two_different_queries() -> None:
    """Two capabilities, two catalogues over the same table (research R-22)."""
    from app.adapters.llm.capabilities import offerable_for

    generation = offerable_for(Capability.GENERATION)
    embeddings = offerable_for(Capability.EMBEDDINGS)

    assert all(row.structured_output for row in generation)
    assert all(row.embeddings for row in embeddings)


def test_anthropic_declares_no_embeddings_instead_of_leaving_it_unverified() -> None:
    """«No lo ofrece» and «sin verificar» are different claims (ADR-011)."""
    from app.adapters.llm.capabilities import ProviderId, capabilities_of

    row = capabilities_of(ProviderId.ANTHROPIC)

    assert row.embeddings is False
    assert row.embedding_dim is None


def test_google_is_the_only_row_verified_and_it_carries_its_date() -> None:
    from app.adapters.llm.capabilities import CAPABILITY_MATRIX, ProviderId, capabilities_of

    verified = [row for row in CAPABILITY_MATRIX if row.verified_on is not None]
    assert [row.provider for row in verified] == [ProviderId.GOOGLE]

    row = capabilities_of(ProviderId.GOOGLE)
    assert row.verified_on == date(2026, 8, 21)
    assert row.structured_output is True
    assert row.respects_null_in_optionals is True
    assert row.embeddings is True
    # MRL truncation from the 3072 the model returns by default (research R-12).
    assert row.embedding_dim == 768


def test_an_unverified_row_claims_nothing_it_has_not_measured() -> None:
    from app.adapters.llm.capabilities import CAPABILITY_MATRIX, ProviderId

    for row in CAPABILITY_MATRIX:
        if row.verified_on is not None or row.provider is ProviderId.ANTHROPIC:
            continue
        assert row.structured_output is None
        assert row.respects_null_in_optionals is None
        assert row.embeddings is None
        assert row.embedding_dim is None


def test_the_matrix_is_data_and_cannot_be_edited_at_runtime() -> None:
    """A verification is a fact of the repository, not of a running process."""
    from app.adapters.llm.capabilities import CAPABILITY_MATRIX

    assert isinstance(CAPABILITY_MATRIX, tuple)
    with pytest.raises(FrozenInstanceError):
        CAPABILITY_MATRIX[0].verified_on = date.today()  # type: ignore[misc]


def test_a_provider_that_respects_no_nulls_is_not_offered_for_generation() -> None:
    """Art. IV: filling optionals with plausible text is the expensive failure.

    A provider can produce perfectly valid structured output and still invent a
    phone number that was never in the CV. That does not break the parse; it
    produces claims with nothing behind them, which is exactly what the
    verifier of art. IV exists to stop.
    """
    from app.adapters.llm.capabilities import offerable_for

    assert all(row.respects_null_in_optionals for row in offerable_for(Capability.GENERATION))
