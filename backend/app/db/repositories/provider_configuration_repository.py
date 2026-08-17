"""One row per capability, so generation and embeddings are truly independent.

Rows and not columns is what makes the independence real: each capability is
configured, verified and invalidated on its own, and a rejected key for one says
nothing about the other (ADR-011, FR-004).

There is no credential column here, encrypted or otherwise. The key lives in
local configuration and only its fingerprint is stored, which is what lets a
rotation invalidate the preflight instead of leaving a result that lies
(FR-008, research R-24).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.db.models.provider_configuration import ProviderConfiguration
from app.db.repositories.base import CandidateScopedRepository
from app.domain.capability import Capability


class ProviderConfigurationRepository(CandidateScopedRepository[ProviderConfiguration]):
    """Reads and writes `provider_configurations`, always scoped by owner."""

    model = ProviderConfiguration

    def for_capability(
        self, candidate_id: UUID, capability: Capability
    ) -> ProviderConfiguration | None:
        statement = select(ProviderConfiguration).filter_by(
            candidate_id=candidate_id, capability=capability.value
        )
        row: ProviderConfiguration | None = self.session.execute(statement).scalar_one_or_none()
        return row

    def save_preflight(
        self,
        candidate_id: UUID,
        *,
        capability: Capability,
        provider: str,
        model: str,
        result: str,
        credential_fingerprint: str,
        embedding_dim: int | None = None,
        at: datetime | None = None,
    ) -> ProviderConfiguration:
        """Record the outcome of a preflight, replacing whatever was there.

        A new preflight **always clears the degradation acknowledgement**: it was
        given for a specific degradation, of a specific key, and carrying it over
        to a new result would let a "yes, I understand what I lose" from before
        cover something the candidate never saw (FR-007.3, SC-016).
        """
        now = datetime.now(UTC)
        row = self.for_capability(candidate_id, capability)
        if row is None:
            # Built complete before it is added: the row has NOT NULL columns
            # for every field of a preflight, so an empty insert followed by
            # assignments would hit the flush with nulls in all of them.
            return self.add(
                candidate_id,
                ProviderConfiguration(
                    capability=capability.value,
                    provider=provider,
                    model=model,
                    preflight_result=result,
                    preflight_at=at or now,
                    credential_fingerprint=credential_fingerprint,
                    embedding_dim=embedding_dim,
                ),
            )

        row.provider = provider
        row.model = model
        row.preflight_result = result
        row.preflight_at = at or now
        row.credential_fingerprint = credential_fingerprint
        row.embedding_dim = embedding_dim
        row.degradation_acknowledged_at = None
        row.updated_at = now
        self.session.flush()
        return row

    def acknowledge_degradation(
        self, candidate_id: UUID, capability: Capability, *, at: datetime | None = None
    ) -> ProviderConfiguration | None:
        """The only way a `capability_unverified` capability becomes usable.

        The database refuses the acknowledgement on any other result
        (`degradation_ack_only_when_unverified`), so silent degradation cannot
        even be represented — this method just declines to try (FR-007.3).
        """
        row = self.for_capability(candidate_id, capability)
        if row is None:
            return None

        row.degradation_acknowledged_at = at or datetime.now(UTC)
        row.updated_at = datetime.now(UTC)
        self.session.flush()
        return row
