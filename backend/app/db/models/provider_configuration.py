"""One row per capability, so generation and embeddings are truly independent."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import pg_enum


class ProviderConfiguration(Base):
    __tablename__ = "provider_configurations"
    __table_args__ = (
        sa.UniqueConstraint(
            "candidate_id",
            "capability",
            name="uq_provider_configurations_candidate_id_capability",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    candidate_id: Mapped[UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("candidates.id", ondelete="CASCADE"),
    )
    capability: Mapped[str] = mapped_column(pg_enum("capability"))
    # Text and not a database enum on purpose: the closed list lives in the
    # capability matrix, where it can carry verified_on, dimension and price. A
    # verification is data, not a schema change (research R-22).
    provider: Mapped[str] = mapped_column(sa.Text())
    model: Mapped[str] = mapped_column(sa.Text())

    preflight_result: Mapped[str] = mapped_column(pg_enum("preflight_result"))
    preflight_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True))
    # HMAC-SHA256 truncated with a locally derived key: not the credential and
    # not a fragment of it. It exists so rotating the key invalidates the
    # preflight instead of leaving a persisted result that lies (research R-24).
    credential_fingerprint: Mapped[str] = mapped_column(sa.Text())

    embedding_dim: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    degradation_acknowledged_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.text("now()"),
    )
