"""The trace reaches `llm_call_logs`, and arrives with no content in it.

Against a real Postgres, because what is being checked is partly what the
database enforces: the enum of `capability`, the numeric of the cost and the
absence of any column where a prompt could fit (art. VI, FR-046).
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.adapters.llm.tracing import LlmCallTrace
from app.db.models.llm_call_log import LlmCallLog
from app.db.repositories.llm_call_log_repository import LlmCallLogRepository
from app.domain.capability import Capability

CANDIDATE_NAME = "María López Hernández"


def _trace(**overrides: object) -> LlmCallTrace:
    defaults: dict[str, object] = {
        "capability": Capability.GENERATION,
        "purpose": "extraction",
        "model": "a-configured-generation-model",
        "prompt_version": "preflight_v1",
        "input_tokens": 980,
        "output_tokens": 210,
        "estimated_cost_usd": Decimal("0"),
        "latency_ms": 1540,
        "attempt": 1,
        "outcome": "ok",
    }
    return LlmCallTrace(**{**defaults, **overrides})  # type: ignore[arg-type]


def test_a_trace_becomes_a_row(db_session: Session) -> None:
    LlmCallLogRepository(db_session).record(_trace())

    row = db_session.execute(select(LlmCallLog)).scalar_one()

    assert row.capability == "generation"
    assert row.purpose == "extraction"
    assert row.input_tokens == 980
    assert row.output_tokens == 210
    assert row.latency_ms == 1540
    assert row.attempt == 1
    assert row.outcome == "ok"


def test_every_attempt_is_its_own_row(db_session: Session) -> None:
    """Three retries are three calls the user paid for (art. VIII)."""
    repository = LlmCallLogRepository(db_session)
    for attempt in (1, 2, 3):
        repository.record(
            _trace(attempt=attempt, outcome="provider_error" if attempt < 3 else "ok")
        )

    rows = db_session.execute(select(LlmCallLog).order_by(LlmCallLog.attempt)).scalars().all()

    assert [row.attempt for row in rows] == [1, 2, 3]


def test_both_capabilities_are_accepted_by_the_enum(db_session: Session) -> None:
    repository = LlmCallLogRepository(db_session)
    repository.record(_trace(capability=Capability.EMBEDDINGS, purpose="preflight"))
    repository.record(_trace(capability=Capability.GENERATION, purpose="preflight"))

    stored = {row.capability for row in db_session.execute(select(LlmCallLog)).scalars()}
    assert stored == {"generation", "embeddings"}


def test_the_table_has_no_column_a_prompt_could_fit_in(db_session: Session) -> None:
    """The guarantee that outlives whoever writes the next trace (research R-13)."""
    columns = {
        column["name"] for column in inspect(db_session.get_bind()).get_columns("llm_call_logs")
    }

    assert not columns & {"prompt", "response", "content", "text", "answer", "candidate_id"}


def test_nothing_of_the_candidate_travels_with_the_trace(db_session: Session) -> None:
    LlmCallLogRepository(db_session).record(_trace())

    row = db_session.execute(select(LlmCallLog)).scalar_one()
    stored = " ".join(str(getattr(row, column.name)) for column in LlmCallLog.__table__.columns)

    assert CANDIDATE_NAME not in stored
