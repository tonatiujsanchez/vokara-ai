"""Cost, latency and prompt version per call — and nothing else (art. VIII).

Articles VIII and V do not actually collide here. Article VIII asks for cost,
latency and prompt version, and that is exactly what this records. Sending the
bodies to a third party is what article V forbids, and it is not needed for
anything article VIII requires (research R-13).

So the record has **no field for content**. Not a redacted one, not a truncated
one: none. A prompt of Vokara carries the candidate's entire CV, which is PII
from beginning to end, and the same reasoning is why Langfuse, LangSmith and
every LLM-observability platform are discarded whether hosted or self-hosted —
their value is precisely in storing what cannot be stored here.

In local execution these traces are **for the user**: they are the substrate of
the accumulated real cost of roadmap §11.3. That is also why every attempt is
recorded separately: three retries are three calls the user pays for.

Where the record goes is not this module's business. It always goes to the
local structured log, and to whatever sinks the composition root registered —
which is how the row in `llm_call_logs` gets written without an adapter
importing the database (art. II).
"""

from __future__ import annotations

import functools
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from pydantic import ValidationError

from app.adapters.llm.base import Purpose
from app.core.logging import get_logger
from app.domain.capability import Capability

logger = get_logger(__name__)

# What the database stores in `llm_call_logs.outcome`.
OUTCOME_OK = "ok"
OUTCOME_SCHEMA_ERROR = "schema_error"
OUTCOME_PROVIDER_ERROR = "provider_error"
OUTCOME_TIMEOUT = "timeout"


@dataclass(frozen=True)
class TokenUsage:
    """What the provider reported spending. Zero when it reported nothing."""

    input_tokens: int = 0
    output_tokens: int = 0


NO_USAGE = TokenUsage()


@dataclass(frozen=True)
class ProviderAnswer[T]:
    """A provider's answer together with what it cost to get it.

    The two travel together so the trace never has to reach back into the
    provider's response object — which is also the object that holds the text.
    """

    value: T
    usage: TokenUsage = NO_USAGE


@dataclass(frozen=True)
class LlmCallTrace:
    """One attempt. Every field here is metadata; there is no room for content."""

    capability: Capability
    purpose: Purpose
    model: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: Decimal
    latency_ms: int
    attempt: int
    outcome: str
    parse_job_id: UUID | None = None


@runtime_checkable
class LlmCallTraceSink(Protocol):
    """Somewhere a trace can be written. The database is one; there may be none."""

    def record(self, trace: LlmCallTrace) -> None: ...


_sinks: list[LlmCallTraceSink] = []


def register_trace_sink(sink: LlmCallTraceSink) -> None:
    """Wire a destination at startup. Registering the same one twice is a no-op."""
    if sink not in _sinks:
        _sinks.append(sink)


def clear_trace_sinks() -> None:
    _sinks.clear()


def estimate_cost_usd(model: str, usage: TokenUsage) -> Decimal:
    """Cost of one call, once there is a rate table to compute it with.

    The rates belong to step 10 of the roadmap, outside this spec (research
    R-27), so today this is zero and the tokens are recorded truthfully — which
    is what makes the cost computable retroactively over traces already stored,
    instead of guessed now.
    """
    del model, usage
    return Decimal("0")


def emit(trace: LlmCallTrace) -> None:
    """To the local log always, and to every registered sink.

    A sink that fails must never fail the call it was observing: losing a trace
    is bad, losing the parse of someone's CV because a trace could not be
    written is worse.
    """
    logger.info(
        "llm_call",
        capability=trace.capability.value,
        purpose=trace.purpose,
        model=trace.model,
        prompt_version=trace.prompt_version,
        input_tokens=trace.input_tokens,
        output_tokens=trace.output_tokens,
        estimated_cost_usd=str(trace.estimated_cost_usd),
        latency_ms=trace.latency_ms,
        attempt=trace.attempt,
        outcome=trace.outcome,
    )

    for sink in _sinks:
        try:
            sink.record(trace)
        except Exception as error:
            logger.warning(
                "llm_trace_sink_failed",
                sink=type(sink).__name__,
                error_type=type(error).__name__,
            )


def _outcome_of(error: BaseException) -> str:
    """How the attempt ended, in terms the database column understands.

    Deliberately provider-agnostic: it reads the shape of the failure, never
    the name of who produced it (art. XI).
    """
    if isinstance(error, ValidationError):
        return OUTCOME_SCHEMA_ERROR
    if isinstance(error, TimeoutError):
        return OUTCOME_TIMEOUT
    if type(error).__name__ in {"OutputParserException", "StructuredOutputMissingError"}:
        return OUTCOME_SCHEMA_ERROR
    return OUTCOME_PROVIDER_ERROR


def traced[T](
    *,
    capability: Capability,
    purpose: Purpose,
    model: str,
    prompt_version: str,
    attempt: int,
    parse_job_id: UUID | None = None,
) -> Callable[[Callable[[], Awaitable[ProviderAnswer[T]]]], Callable[[], Awaitable[T]]]:
    """Wrap one attempt so it is measured whether it succeeds or fails.

    A failed call still costs latency and often tokens, and it is the one the
    user is waiting on — tracing only the happy path would lose exactly the
    line the diagnostics screen needs.
    """

    def decorate(call: Callable[[], Awaitable[ProviderAnswer[T]]]) -> Callable[[], Awaitable[T]]:
        @functools.wraps(call)
        async def wrapper() -> T:
            started = time.perf_counter()
            usage = NO_USAGE
            outcome = OUTCOME_OK
            try:
                answer = await call()
                usage = answer.usage
                return answer.value
            except BaseException as error:
                outcome = _outcome_of(error)
                raise
            finally:
                emit(
                    LlmCallTrace(
                        capability=capability,
                        purpose=purpose,
                        model=model,
                        prompt_version=prompt_version,
                        input_tokens=usage.input_tokens,
                        output_tokens=usage.output_tokens,
                        estimated_cost_usd=estimate_cost_usd(model, usage),
                        latency_ms=int((time.perf_counter() - started) * 1000),
                        attempt=attempt,
                        outcome=outcome,
                        parse_job_id=parse_job_id,
                    )
                )

        return wrapper

    return decorate


def usage_from_provider_metadata(raw: Any) -> TokenUsage:  # noqa: ANN401 — provider payload
    """Token counts if the provider reported them, zeros if it did not.

    Only the two integers are read. The object this comes from also holds the
    answer text, and the fact that it is never touched here is the point.
    """
    metadata = getattr(raw, "usage_metadata", None)
    if not isinstance(metadata, dict):
        return NO_USAGE

    input_tokens = metadata.get("input_tokens", 0)
    output_tokens = metadata.get("output_tokens", 0)
    return TokenUsage(
        input_tokens=input_tokens if isinstance(input_tokens, int) else 0,
        output_tokens=output_tokens if isinstance(output_tokens, int) else 0,
    )
