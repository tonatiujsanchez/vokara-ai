"""The first run as a whole: the acknowledgement, the state, the conclusion.

Three things live here and each one is a requirement rather than a convenience:

- **The acknowledgement is recorded with its timestamp and the version accepted**
  (FR-002, research R-29). Which text was accepted matters as much as that it
  was, because a future change in what Vokara sends to the provider must be able
  to demand a new one instead of being covered by an old yes.
- **The state is assembled, never stored.** `pending_step` and `is_complete` are
  derived by `domain/setup.py` from the facts each repository holds, so nothing
  can drift out of sync with reality (research R-18).
- **The gate is on the server** (SC-011). `require_disclosure_acknowledgement` is
  what the upload of a CV will call: without the acknowledgement on record no
  endpoint of the onboarding answers, whether the caller is the SPA, a reload or
  a curl. The guard in the frontend is convenience; this is the control.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.core.config import Settings, get_settings
from app.db.repositories.setup_state_repository import SetupStateRepository
from app.db.session import session_scope
from app.domain.capability import Capability
from app.domain.disclosure import CURRENT_DISCLOSURE
from app.domain.errors import (
    DisclosureAcknowledgementRequiredError,
    DisclosureAlreadyAcknowledgedError,
)
from app.domain.setup import (
    EmailStepStatus,
    SetupFacts,
    SetupStep,
    is_complete,
    pending_step,
)
from app.services.preflight_service import (
    ProviderConfigurationView,
    current_configuration,
)


@dataclass(frozen=True)
class DisclosureView:
    """The full text plus what is known about its acknowledgement (FR-001)."""

    version: str
    body_md: str
    acknowledged: bool
    acknowledged_at: datetime | None
    acknowledged_version: str | None


@dataclass(frozen=True)
class SetupStateView:
    """Every fact of the first run, and the two values derived from them.

    It carries no credential and no fingerprint: what the API may say about a
    credential is the three-valued status inside each configuration, and nothing
    else (FR-008, SC-013).
    """

    pending_step: SetupStep | None
    disclosure_acknowledged: bool
    disclosure_acknowledged_at: datetime | None
    generation: ProviderConfigurationView | None
    embeddings: ProviderConfigurationView | None
    email_status: EmailStepStatus
    is_complete: bool


def _acknowledgement(candidate_id: UUID) -> tuple[datetime | None, str | None, EmailStepStatus]:
    with session_scope() as session:
        row = SetupStateRepository(session).for_candidate(candidate_id)
        if row is None:
            return None, None, EmailStepStatus.PENDING
        return (
            row.disclosure_acknowledged_at,
            row.disclosure_version,
            EmailStepStatus(row.email_step_status),
        )


def read_disclosure(candidate_id: UUID) -> DisclosureView:
    """The current text, whole, with the state of its acknowledgement.

    The body travels complete because art. V forbids the disclosure being only a
    link or only the README: the screen has to be able to show all of it without
    a second request.
    """
    acknowledged_at, acknowledged_version, _ = _acknowledgement(candidate_id)

    return DisclosureView(
        version=CURRENT_DISCLOSURE.version,
        body_md=CURRENT_DISCLOSURE.body_md,
        acknowledged=CURRENT_DISCLOSURE.covers(acknowledged_version),
        acknowledged_at=acknowledged_at,
        acknowledged_version=acknowledged_version,
    )


def acknowledge_disclosure(
    candidate_id: UUID, *, version: str, settings: Settings | None = None
) -> SetupStateView:
    """Record an explicit, affirmative acknowledgement of the current text.

    Acknowledging a version that is not the current one is refused rather than
    accepted-and-ignored: it would leave a record saying the candidate accepted
    something they were not shown (FR-002, research R-29).
    """
    if not CURRENT_DISCLOSURE.covers(version):
        raise DisclosureAcknowledgementRequiredError

    _, acknowledged_version, _ = _acknowledgement(candidate_id)
    if CURRENT_DISCLOSURE.covers(acknowledged_version):
        raise DisclosureAlreadyAcknowledgedError

    with session_scope() as session:
        SetupStateRepository(session).record_disclosure_acknowledgement(
            candidate_id, version=version
        )

    return read_state(candidate_id, settings)


def read_state(candidate_id: UUID, settings: Settings | None = None) -> SetupStateView:
    """Assemble the facts and derive the two answers the wizard needs."""
    resolved = settings or get_settings()
    acknowledged_at, acknowledged_version, email_status = _acknowledgement(candidate_id)

    generation = current_configuration(candidate_id, Capability.GENERATION, resolved)
    embeddings = current_configuration(candidate_id, Capability.EMBEDDINGS, resolved)

    facts = SetupFacts(
        current_disclosure_version=CURRENT_DISCLOSURE.version,
        acknowledged_disclosure_version=acknowledged_version,
        generation=generation.as_facts() if generation else None,
        embeddings=embeddings.as_facts() if embeddings else None,
        email_status=email_status,
    )

    return SetupStateView(
        pending_step=pending_step(facts),
        disclosure_acknowledged=facts.disclosure_acknowledged,
        disclosure_acknowledged_at=acknowledged_at,
        generation=generation,
        embeddings=embeddings,
        email_status=email_status,
        is_complete=is_complete(facts),
    )


def require_disclosure_acknowledgement(candidate_id: UUID) -> None:
    """The server gate of SC-011: no route reaches the onboarding without it.

    Called by the endpoints of the onboarding rather than by the wizard, which
    is the point — a guard that only the SPA enforces is not a guard.
    """
    _, acknowledged_version, _ = _acknowledgement(candidate_id)
    if not CURRENT_DISCLOSURE.covers(acknowledged_version):
        raise DisclosureAcknowledgementRequiredError
