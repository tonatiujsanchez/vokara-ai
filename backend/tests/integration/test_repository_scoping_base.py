"""Scoping verified with two candidate_ids, not one (research R-11, FR-049).

Only one value can exist in a real installation, which is precisely why the
test seeds two: with a single id every query looks correctly scoped, including
the ones that are not scoped at all. Two ids make the discipline executable
instead of a verbal agreement (ADR-008, "Costos y riesgos").
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from app.db.models import Candidate, Document, ProviderConfiguration
from app.db.repositories.base import CandidateScopedRepository


class DocumentRepository(CandidateScopedRepository[Document]):
    model = Document


class ProviderConfigurationRepository(CandidateScopedRepository[ProviderConfiguration]):
    model = ProviderConfiguration


@pytest.fixture
def two_candidates(db_session: Session) -> tuple[UUID, UUID]:
    first, second = Candidate(), Candidate()
    db_session.add_all([first, second])
    db_session.flush()
    return first.id, second.id


def make_document(filename: str) -> Document:
    return Document(
        kind="pdf",
        original_filename=filename,
        size_bytes=1024,
        sha256=uuid4().hex,
        storage_key=uuid4().hex,
    )


def test_list_only_returns_what_belongs_to_the_owner(
    db_session: Session, two_candidates: tuple[UUID, UUID]
) -> None:
    mine, theirs = two_candidates
    repository = DocumentRepository(db_session)

    repository.add(mine, make_document("mio.pdf"))
    repository.add(mine, make_document("mio-2.pdf"))
    repository.add(theirs, make_document("ajeno.pdf"))

    assert sorted(document.original_filename for document in repository.list(mine)) == [
        "mio-2.pdf",
        "mio.pdf",
    ]
    assert [document.original_filename for document in repository.list(theirs)] == ["ajeno.pdf"]
    assert repository.count(mine) == 2
    assert repository.count(theirs) == 1


def test_a_resource_of_another_owner_is_absent_not_forbidden(
    db_session: Session, two_candidates: tuple[UUID, UUID]
) -> None:
    """None here becomes 404 at the API, never 403 (FR-049)."""
    mine, theirs = two_candidates
    repository = DocumentRepository(db_session)

    theirs_document = repository.add(theirs, make_document("ajeno.pdf"))

    assert repository.get(theirs, theirs_document.id) is not None
    assert repository.get(mine, theirs_document.id) is None
    assert repository.exists(mine, theirs_document.id) is False


def test_scoping_holds_for_every_model_that_uses_the_base(
    db_session: Session, two_candidates: tuple[UUID, UUID]
) -> None:
    mine, theirs = two_candidates
    repository = ProviderConfigurationRepository(db_session)

    for owner, provider in ((mine, "mio"), (theirs, "ajeno")):
        repository.add(
            owner,
            ProviderConfiguration(
                capability="generation",
                provider=provider,
                model="un-modelo",
                preflight_result="verified",
                preflight_at=datetime.now(UTC),
                credential_fingerprint="digest",
            ),
        )

    assert [row.provider for row in repository.list(mine)] == ["mio"]
    assert [row.provider for row in repository.list(theirs)] == ["ajeno"]


def test_add_stamps_the_owner_so_it_cannot_be_forgotten(
    db_session: Session, two_candidates: tuple[UUID, UUID]
) -> None:
    mine, _ = two_candidates
    repository = DocumentRepository(db_session)

    stored = repository.add(mine, make_document("mio.pdf"))

    assert stored.candidate_id == mine
