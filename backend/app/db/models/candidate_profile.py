"""The master profile: the single source of truth about the candidate (ADR-005)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import pg_enum


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    candidate_id: Mapped[UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("candidates.id", ondelete="CASCADE"),
        unique=True,
    )

    # Only confirmation_service writes this, and the database refuses
    # `complete` without a version (art. X, FR-038, SC-001).
    state: Mapped[str] = mapped_column(
        pg_enum("profile_state"),
        server_default=sa.text("'draft'::profile_state"),
    )
    current_version_id: Mapped[UUID | None] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey(
            "profile_versions.id",
            name="fk_candidate_profiles_current_version_id_profile_versions",
            use_alter=True,
        ),
        nullable=True,
    )
    last_confirmed_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
    )

    # ── Objectives (FR-035) ───────────────────────────────────────────────
    # Typed columns rather than JSONB: matching queries them and they carry real
    # business validation (research R-17).
    target_role: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    salary_min: Mapped[Decimal | None] = mapped_column(sa.Numeric(12, 2), nullable=True)
    salary_max: Mapped[Decimal | None] = mapped_column(sa.Numeric(12, 2), nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(sa.CHAR(3), nullable=True)
    remote_preference: Mapped[str | None] = mapped_column(
        pg_enum("remote_preference"),
        nullable=True,
    )
    locations: Mapped[list[str]] = mapped_column(
        postgresql.ARRAY(sa.Text()),
        server_default=sa.text("'{}'::text[]"),
    )
    industries: Mapped[list[str]] = mapped_column(
        postgresql.ARRAY(sa.Text()),
        server_default=sa.text("'{}'::text[]"),
    )
    deal_breakers: Mapped[list[str]] = mapped_column(
        postgresql.ARRAY(sa.Text()),
        server_default=sa.text("'{}'::text[]"),
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.text("now()"),
    )
