"""Two candidate_ids, against real Postgres (research R-11, art. VI).

Only one owner can exist in a real installation, which is precisely why the test
seeds two: with a single id every query looks correctly scoped, including the
ones that are not scoped at all.

Real Postgres and not a double because half of what is being checked is what the
database itself enforces — the 1:1 uniqueness of `setup_state`, the uniqueness of
(candidate_id, capability), and the CHECKs that make silent degradation
impossible to represent (data-model.md).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Candidate
from app.db.repositories.provider_configuration_repository import (
    ProviderConfigurationRepository,
)
from app.db.repositories.setup_state_repository import SetupStateRepository
from app.domain.capability import (
    Capability,
    CapabilityUnverified,
    CredentialRejected,
    Verified,
)

VERSION = "2026-08-17"


@pytest.fixture
def two_candidates(db_session: Session) -> tuple[UUID, UUID]:
    mine, theirs = Candidate(), Candidate()
    db_session.add_all([mine, theirs])
    db_session.flush()
    return mine.id, theirs.id


# ── setup_state ─────────────────────────────────────────────────────────────


def test_the_row_is_created_once_and_found_again(
    db_session: Session, two_candidates: tuple[UUID, UUID]
) -> None:
    mine, _ = two_candidates
    repository = SetupStateRepository(db_session)

    first = repository.ensure(mine)
    again = repository.ensure(mine)

    assert first.id == again.id
    assert repository.count(mine) == 1


def test_an_acknowledgement_belongs_to_one_owner_only(
    db_session: Session, two_candidates: tuple[UUID, UUID]
) -> None:
    mine, theirs = two_candidates
    repository = SetupStateRepository(db_session)

    repository.record_disclosure_acknowledgement(mine, version=VERSION)
    repository.ensure(theirs)

    assert repository.for_candidate(mine).disclosure_version == VERSION  # type: ignore[union-attr]
    assert repository.for_candidate(theirs).disclosure_version is None  # type: ignore[union-attr]


def test_the_acknowledgement_carries_its_date_and_its_version(
    db_session: Session, two_candidates: tuple[UUID, UUID]
) -> None:
    """Knowing what was accepted matters as much as that it was (research R-29)."""
    mine, _ = two_candidates

    row = SetupStateRepository(db_session).record_disclosure_acknowledgement(mine, version=VERSION)

    assert row.disclosure_acknowledged_at is not None
    assert row.disclosure_version == VERSION


def test_linking_records_the_label_and_skipping_erases_it(
    db_session: Session, two_candidates: tuple[UUID, UUID]
) -> None:
    """Both endings are valid, and the database checks each one's shape."""
    mine, theirs = two_candidates
    repository = SetupStateRepository(db_session)

    linked = repository.record_email_linked(mine, label="Alertas de empleo")
    skipped = repository.record_email_skipped(theirs)
    db_session.flush()

    assert (linked.email_step_status, linked.email_label) == ("linked", "Alertas de empleo")
    assert (skipped.email_step_status, skipped.email_label) == ("skipped", None)
    assert skipped.email_linked_at is None


def test_the_stored_row_holds_nothing_that_could_be_a_credential(
    db_session: Session, two_candidates: tuple[UUID, UUID]
) -> None:
    """FR-013: the App Password lives in local configuration, never here."""
    mine, _ = two_candidates
    repository = SetupStateRepository(db_session)

    repository.record_email_linked(mine, label="Alertas de empleo")

    columns = {column.name for column in repository.for_candidate(mine).__table__.columns}  # type: ignore[union-attr]
    assert not columns & {"app_password", "password", "api_key", "credential", "secret"}


# ── provider_configurations ─────────────────────────────────────────────────


def test_each_capability_is_its_own_row_per_owner(
    db_session: Session, two_candidates: tuple[UUID, UUID]
) -> None:
    mine, theirs = two_candidates
    repository = ProviderConfigurationRepository(db_session)

    for owner, provider in ((mine, "mio"), (theirs, "ajeno")):
        for capability in Capability:
            repository.save_preflight(
                owner,
                capability=capability,
                provider=provider,
                model="un-modelo",
                result=Verified.result,
                credential_fingerprint="digest",
                embedding_dim=768 if capability is Capability.EMBEDDINGS else None,
            )

    assert repository.count(mine) == 2
    assert {row.provider for row in repository.list(mine)} == {"mio"}
    assert repository.for_capability(theirs, Capability.GENERATION).provider == "ajeno"  # type: ignore[union-attr]


def test_a_configuration_of_another_owner_is_absent_not_forbidden(
    db_session: Session, two_candidates: tuple[UUID, UUID]
) -> None:
    """None here becomes 404 at the API, never 403 (FR-049)."""
    mine, theirs = two_candidates
    repository = ProviderConfigurationRepository(db_session)

    repository.save_preflight(
        theirs,
        capability=Capability.GENERATION,
        provider="ajeno",
        model="un-modelo",
        result=Verified.result,
        credential_fingerprint="digest",
    )

    assert repository.for_capability(mine, Capability.GENERATION) is None


def test_saving_again_replaces_the_result_instead_of_adding_a_row(
    db_session: Session, two_candidates: tuple[UUID, UUID]
) -> None:
    mine, _ = two_candidates
    repository = ProviderConfigurationRepository(db_session)

    repository.save_preflight(
        mine,
        capability=Capability.GENERATION,
        provider="mio",
        model="un-modelo",
        result=CredentialRejected.result,
        credential_fingerprint="viejo",
    )
    repository.save_preflight(
        mine,
        capability=Capability.GENERATION,
        provider="mio",
        model="un-modelo",
        result=Verified.result,
        credential_fingerprint="nuevo",
    )

    row = repository.for_capability(mine, Capability.GENERATION)
    assert repository.count(mine) == 1
    assert (row.preflight_result, row.credential_fingerprint) == (Verified.result, "nuevo")  # type: ignore[union-attr]


def test_a_new_preflight_clears_the_previous_degradation_acknowledgement(
    db_session: Session, two_candidates: tuple[UUID, UUID]
) -> None:
    """The yes was given for a degradation nobody has seen twice (SC-016)."""
    mine, _ = two_candidates
    repository = ProviderConfigurationRepository(db_session)

    repository.save_preflight(
        mine,
        capability=Capability.GENERATION,
        provider="mio",
        model="un-modelo",
        result=CapabilityUnverified.result,
        credential_fingerprint="viejo",
    )
    repository.acknowledge_degradation(mine, Capability.GENERATION)
    repository.save_preflight(
        mine,
        capability=Capability.GENERATION,
        provider="mio",
        model="otro-modelo",
        result=CapabilityUnverified.result,
        credential_fingerprint="nuevo",
    )

    row = repository.for_capability(mine, Capability.GENERATION)
    assert row.degradation_acknowledged_at is None  # type: ignore[union-attr]


def test_the_database_refuses_an_acknowledgement_on_any_other_result(
    db_session: Session, two_candidates: tuple[UUID, UUID]
) -> None:
    """Silent degradation is not just forbidden: it cannot be represented."""
    mine, _ = two_candidates
    repository = ProviderConfigurationRepository(db_session)

    repository.save_preflight(
        mine,
        capability=Capability.GENERATION,
        provider="mio",
        model="un-modelo",
        result=Verified.result,
        credential_fingerprint="digest",
    )

    with pytest.raises(IntegrityError):
        repository.acknowledge_degradation(mine, Capability.GENERATION)


def test_a_verified_embeddings_without_its_dimension_is_refused(
    db_session: Session, two_candidates: tuple[UUID, UUID]
) -> None:
    """FR-007.2: that number ends up beside every future vector (ADR-003)."""
    mine, _ = two_candidates
    repository = ProviderConfigurationRepository(db_session)

    with pytest.raises(IntegrityError):
        repository.save_preflight(
            mine,
            capability=Capability.EMBEDDINGS,
            provider="mio",
            model="un-modelo",
            result=Verified.result,
            credential_fingerprint="digest",
            embedding_dim=None,
        )


def test_the_table_has_no_column_a_credential_could_fit_in(
    db_session: Session, two_candidates: tuple[UUID, UUID]
) -> None:
    """The guarantee that outlives whoever writes the next endpoint (FR-008)."""
    mine, _ = two_candidates
    repository = ProviderConfigurationRepository(db_session)

    row = repository.save_preflight(
        mine,
        capability=Capability.GENERATION,
        provider="mio",
        model="un-modelo",
        result=Verified.result,
        credential_fingerprint="digest",
        at=datetime.now(UTC),
    )

    columns = {column.name for column in row.__table__.columns}
    assert not columns & {"api_key", "credential", "secret", "token", "password"}
