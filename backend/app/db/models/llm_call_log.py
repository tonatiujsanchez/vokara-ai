"""Cost, latency and prompt version per LLM call (art. VIII, FR-046).

No PII and no credentials by design: no prompts, no responses, no candidate
identifier. Any PR adding a column with free text from the document violates
art. V, and there is nowhere here to put it (research R-13).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import pg_enum


class LlmCallLog(Base):
    __tablename__ = "llm_call_logs"

    id: Mapped[UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    parse_job_id: Mapped[UUID | None] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("parse_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )

    # classification | extraction | preflight
    purpose: Mapped[str] = mapped_column(sa.Text())
    # Separating generation cost from embeddings cost is what makes the
    # estimate of FR-005 checkable against reality later.
    capability: Mapped[str] = mapped_column(pg_enum("capability"))
    model: Mapped[str] = mapped_column(sa.Text())
    prompt_version: Mapped[str] = mapped_column(sa.Text())

    input_tokens: Mapped[int] = mapped_column(sa.Integer())
    output_tokens: Mapped[int] = mapped_column(sa.Integer())
    estimated_cost_usd: Mapped[Decimal] = mapped_column(sa.Numeric(10, 6))
    latency_ms: Mapped[int] = mapped_column(sa.Integer())
    attempt: Mapped[int] = mapped_column(sa.SmallInteger(), server_default=sa.text("1"))
    # ok | schema_error | provider_error | timeout
    outcome: Mapped[str] = mapped_column(sa.Text())

    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.text("now()"),
    )
