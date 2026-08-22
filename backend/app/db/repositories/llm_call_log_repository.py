"""The sink that turns a trace into the row of `llm_call_logs`.

It lives here and not in the adapter because article II is one-directional: an
adapter never imports the database. The adapter defines what a trace is and
where it can be written; this is one of those places, wired at startup.

Each trace gets **its own transaction**. A trace is not part of the work it
observes: it must survive a parse that is about to fail — which is precisely
the trace someone will want to read — and it must never be what makes that work
fail either (art. VIII).

There is no `candidate_id` here, and that is deliberate rather than an
oversight of the scoping rule: `llm_call_logs` has no such column, because a
trace carries cost and latency and nothing that belongs to a person
(data-model.md, research R-13).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.adapters.llm.tracing import LlmCallTrace
from app.db.models.llm_call_log import LlmCallLog
from app.db.session import session_scope


def to_row(trace: LlmCallTrace) -> LlmCallLog:
    """The trace as a row. Every field maps across; none is left over."""
    return LlmCallLog(
        parse_job_id=trace.parse_job_id,
        purpose=trace.purpose,
        capability=trace.capability.value,
        model=trace.model,
        prompt_version=trace.prompt_version,
        input_tokens=trace.input_tokens,
        output_tokens=trace.output_tokens,
        estimated_cost_usd=trace.estimated_cost_usd,
        latency_ms=trace.latency_ms,
        attempt=trace.attempt,
        outcome=trace.outcome,
    )


class LlmCallLogRepository:
    """Writes traces into a session someone else owns."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def record(self, trace: LlmCallTrace) -> LlmCallLog:
        row = to_row(trace)
        self.session.add(row)
        self.session.flush()
        return row


class DatabaseTraceSink:
    """The `LlmCallTraceSink` the composition root registers at startup."""

    def record(self, trace: LlmCallTrace) -> None:
        with session_scope() as session:
            LlmCallLogRepository(session).record(trace)
