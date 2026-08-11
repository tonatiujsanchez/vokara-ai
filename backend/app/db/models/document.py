"""The original CV. A backup, not the source of truth (FR-018, ADR-005)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import pg_enum


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        sa.Index(
            "ix_documents_candidate_id_uploaded_at",
            "candidate_id",
            sa.text("uploaded_at DESC"),
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

    # Decided by byte signature, never by extension or by the Content-Type the
    # client sends: the signature is the only signal the client does not control
    # (research R-01).
    kind: Mapped[str] = mapped_column(pg_enum("document_kind"))
    original_filename: Mapped[str] = mapped_column(sa.Text())
    size_bytes: Mapped[int] = mapped_column(sa.Integer())
    sha256: Mapped[str] = mapped_column(sa.Text())

    # Never exposed in an API response or an error message: a FileNotFoundError
    # with a path on screen is a product bug (ADR-007, roadmap 11.5).
    storage_key: Mapped[str] = mapped_column(sa.Text())

    # Hooks for feature 006: it will only add enum values, never alter the table
    # or backfill rows.
    availability: Mapped[str] = mapped_column(
        pg_enum("document_availability"),
        server_default=sa.text("'available'::document_availability"),
    )
    availability_changed_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.text("now()"),
    )
