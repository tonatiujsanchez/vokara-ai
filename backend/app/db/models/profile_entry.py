"""Atomic, referenceable entries (FR-024 to FR-028)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import pg_enum


class ProfileEntry(Base):
    __tablename__ = "profile_entries"

    # Stable for life (FR-025): this is the future source_id of art. IV.
    id: Mapped[UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    profile_id: Mapped[UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
    )
    entry_type: Mapped[str] = mapped_column(pg_enum("entry_type"))
    origin: Mapped[str] = mapped_column(pg_enum("entry_origin"))

    # Validated by a discriminated union in domain/entries.py, where every field
    # the document may not carry is optional: the natural output for a missing
    # value is "incomplete entry", never an invented one (art. IV, research R-05).
    content: Mapped[dict[str, Any]] = mapped_column(postgresql.JSONB())
    content_language: Mapped[str | None] = mapped_column(sa.CHAR(2), nullable=True)

    # Computed by rules, never by the model (FR-028).
    is_complete: Mapped[bool] = mapped_column(sa.Boolean())
    missing_fields: Mapped[list[str]] = mapped_column(
        postgresql.ARRAY(sa.Text()),
        server_default=sa.text("'{}'::text[]"),
    )

    source_document_id: Mapped[UUID | None] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    # The literal fragment it came from: cheap, and it makes the evals auditable.
    source_excerpt: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)

    # Logical delete: keeps the diff against the current version correct and
    # lets 007 avoid resurrecting what the candidate deleted (FR-032).
    deleted_at: Mapped[datetime | None] = mapped_column(
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
