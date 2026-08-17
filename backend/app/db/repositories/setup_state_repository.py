"""The single first-run row of an installation, always read by owner.

One row can exist per candidate and today one candidate exists (ADR-008), which
is exactly why `candidate_id` is in every signature: the day authentication
arrives, what changes is where the value comes from, not how the queries are
written (research R-11).

The repository stores facts and nothing else. Which step is pending is derived
from them in `domain/setup.py` and is deliberately not a column (research R-18).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.db.models.setup_state import SetupState
from app.db.repositories.base import CandidateScopedRepository


class SetupStateRepository(CandidateScopedRepository[SetupState]):
    """Reads and writes `setup_state`. Never a credential (FR-008, FR-013)."""

    model = SetupState

    def for_candidate(self, candidate_id: UUID) -> SetupState | None:
        statement = select(SetupState).filter_by(candidate_id=candidate_id)
        row: SetupState | None = self.session.execute(statement).scalar_one_or_none()
        return row

    def ensure(self, candidate_id: UUID) -> SetupState:
        """The row, creating it on first contact with the wizard.

        Created lazily rather than seeded by the migration because an empty row
        and a missing row mean the same thing —nothing acknowledged, nothing
        linked— and a lazy create keeps the migration free of behaviour.
        """
        existing = self.for_candidate(candidate_id)
        if existing is not None:
            return existing
        return self.add(candidate_id, SetupState())

    def record_disclosure_acknowledgement(
        self, candidate_id: UUID, *, version: str, at: datetime | None = None
    ) -> SetupState:
        """The acknowledgement as a fact: a timestamp **and** the version accepted.

        Both or neither, which the database also enforces
        (`disclosure_ack_complete`): a date without a version would not say what
        was accepted, and that is half the point of recording it (research R-29).
        """
        row = self.ensure(candidate_id)
        row.disclosure_acknowledged_at = at or datetime.now(UTC)
        row.disclosure_version = version
        self.session.flush()
        return row

    def record_email_linked(
        self, candidate_id: UUID, *, label: str, at: datetime | None = None
    ) -> SetupState:
        """Linked, with the designated label. Never the App Password (FR-013)."""
        row = self.ensure(candidate_id)
        row.email_step_status = "linked"
        row.email_label = label
        row.email_linked_at = at or datetime.now(UTC)
        self.session.flush()
        return row

    def record_email_skipped(self, candidate_id: UUID) -> SetupState:
        """Skipping leaves no configuration behind, and the database checks it."""
        row = self.ensure(candidate_id)
        row.email_step_status = "skipped"
        row.email_label = None
        row.email_linked_at = None
        self.session.flush()
        return row
