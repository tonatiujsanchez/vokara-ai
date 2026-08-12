"""First-run state: facts, never a "I am on step 2" pointer (research R-18)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import pg_enum


class SetupState(Base):
    __tablename__ = "setup_state"

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

    # The acknowledgement is a fact with a date and the version of the text that
    # was accepted: knowing what someone accepted matters as much as that they
    # did (FR-001, research R-29).
    disclosure_acknowledged_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
    )
    disclosure_version: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)

    email_step_status: Mapped[str] = mapped_column(
        pg_enum("email_step_status"),
        server_default=sa.text("'pending'::email_step_status"),
    )
    # The designated label. Never the App Password: credentials live in local
    # configuration and never touch the database (FR-013, FR-008).
    email_label: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    email_linked_at: Mapped[datetime | None] = mapped_column(
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
