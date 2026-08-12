"""Processing work, with progress the UI can poll (FR-019, FR-023)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import pg_enum


class ParseJob(Base):
    __tablename__ = "parse_jobs"
    __table_args__ = (
        # One active job per candidate, guaranteed by the database rather than
        # by application logic: a Redis semaphore can be orphaned by a dead
        # worker, this index cannot disagree with the state because it is the
        # state (research R-07).
        sa.Index(
            "ux_parse_jobs_one_active",
            "candidate_id",
            unique=True,
            postgresql_where=sa.text("status IN ('queued', 'running')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    # Denormalised on purpose: it is what the uniqueness index stands on.
    candidate_id: Mapped[UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("candidates.id", ondelete="CASCADE"),
    )
    document_id: Mapped[UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("documents.id", ondelete="CASCADE"),
    )

    status: Mapped[str] = mapped_column(
        pg_enum("parse_job_status"),
        server_default=sa.text("'queued'::parse_job_status"),
    )
    step: Mapped[str | None] = mapped_column(pg_enum("parse_job_step"), nullable=True)
    progress_percent: Mapped[int] = mapped_column(sa.SmallInteger(), server_default=sa.text("0"))

    # A stable code from the catalogue. There is no free-text error column, on
    # purpose: that is where a trace with PII would end up (FR-045).
    error_code: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    entries_created: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.text("0"))
    truncated: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.text("false"))

    # Retry is strictly additive: a new job over the same document (FR-023).
    retry_of_job_id: Mapped[UUID | None] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("parse_jobs.id"),
        nullable=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.text("now()"),
    )
