"""Immutable snapshot of a confirmation (FR-040, FR-041, FR-043).

Append-only, enforced by a database trigger rather than by convention: the
repository exposes no write method either, but the trigger is what makes it
true for anything that reaches the database.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import pg_enum


class ProfileVersion(Base):
    __tablename__ = "profile_versions"
    __table_args__ = (
        sa.UniqueConstraint(
            "profile_id",
            "version_number",
            name="uq_profile_versions_profile_id_version_number",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    profile_id: Mapped[UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
    )
    version_number: Mapped[int] = mapped_column(sa.Integer())
    origin: Mapped[str] = mapped_column(pg_enum("version_origin"))

    # The whole entries, not references: a version must stay readable even if an
    # entry is deleted afterwards (FR-041).
    content: Mapped[dict[str, Any]] = mapped_column(postgresql.JSONB())
    # SHA-256 of the canonical serialisation. "You have unconfirmed changes" is
    # derived by comparing this, never kept as a flag (research R-08).
    content_hash: Mapped[str] = mapped_column(sa.Text())

    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.text("now()"),
    )
