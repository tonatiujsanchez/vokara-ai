"""What the trace records, and above all what it cannot record (art. V, FR-046).

The prompts of this feature carry the candidate's whole CV. So the test that
matters is not that the fields are right — it is that a full call, with the CV
in the prompt and the extracted profile in the answer, leaves **no fragment of
either** in the log line or in the row that gets persisted.

Written as an inspection of the record type as well as of the emitted output,
because a field added tomorrow with a plausible name (`prompt`, `snippet`,
`sample`) is exactly how this leak would arrive (research R-13).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import fields
from decimal import Decimal
from io import StringIO
from typing import Any
from uuid import uuid4

import pytest
from pydantic import SecretStr

from app.adapters.llm.base import TraceContext
from app.adapters.llm.google import GoogleStructuredOutput
from app.adapters.llm.prompts.preflight_v2 import INCOMPLETE_CV_SAMPLE, PREFLIGHT_PROMPT_VERSION
from app.adapters.llm.schemas import PreflightExtraction
from app.adapters.llm.tracing import (
    OUTCOME_OK,
    OUTCOME_PROVIDER_ERROR,
    OUTCOME_SCHEMA_ERROR,
    OUTCOME_TIMEOUT,
    LlmCallTrace,
    LlmCallTraceSink,
    ProviderAnswer,
    TokenUsage,
    clear_trace_sinks,
    register_trace_sink,
    traced,
)
from app.core.logging import configure_logging
from app.domain.capability import Capability

MODEL = "a-configured-generation-model"

# The candidate's data, and the provider's answer about it. Neither may appear.
CANDIDATE_NAME = "María López Hernández"
CANDIDATE_PHONE = "+52 55 1234 5678"
ANSWER_TEXT = "Desarrolladora Backend en Tecnologías del Norte"


class CollectingSink:
    """Stands in for the row in `llm_call_logs`, without a database."""

    def __init__(self) -> None:
        self.traces: list[LlmCallTrace] = []

    def record(self, trace: LlmCallTrace) -> None:
        self.traces.append(trace)


@pytest.fixture
def sink() -> Iterator[CollectingSink]:
    collecting = CollectingSink()
    register_trace_sink(collecting)
    yield collecting
    clear_trace_sinks()


@pytest.fixture
def log_stream() -> StringIO:
    stream = StringIO()
    configure_logging(stream=stream)
    return stream


def _trace_call(result: ProviderAnswer[str] | BaseException, attempt: int = 1) -> Any:  # noqa: ANN401
    @traced(
        capability=Capability.GENERATION,
        purpose="extraction",
        model=MODEL,
        prompt_version=PREFLIGHT_PROMPT_VERSION,
        attempt=attempt,
        parse_job_id=uuid4(),
    )
    async def call() -> ProviderAnswer[str]:
        if isinstance(result, BaseException):
            raise result
        return result

    return call


def test_the_record_type_has_nowhere_to_put_content() -> None:
    """The strongest guarantee available: there is no field to leak into."""
    names = {field.name for field in fields(LlmCallTrace)}

    assert names == {
        "capability",
        "purpose",
        "model",
        "prompt_version",
        "input_tokens",
        "output_tokens",
        "estimated_cost_usd",
        "latency_ms",
        "attempt",
        "outcome",
        "parse_job_id",
    }
    assert not [
        name for name in names if any(word in name for word in ("prompt_text", "response", "text"))
    ]


async def test_a_successful_call_records_metadata_and_nothing_else(
    sink: CollectingSink, log_stream: StringIO
) -> None:
    answer = ProviderAnswer(
        value=ANSWER_TEXT, usage=TokenUsage(input_tokens=980, output_tokens=210)
    )

    await _trace_call(answer)()

    (trace,) = sink.traces
    assert trace.outcome == OUTCOME_OK
    assert trace.input_tokens == 980
    assert trace.output_tokens == 210
    assert trace.model == MODEL
    assert trace.prompt_version == PREFLIGHT_PROMPT_VERSION
    assert trace.latency_ms >= 0
    assert isinstance(trace.estimated_cost_usd, Decimal)

    line = json.loads(log_stream.getvalue())
    assert line["event"] == "llm_call"
    assert ANSWER_TEXT not in log_stream.getvalue()


async def test_no_fragment_of_the_cv_or_of_the_answer_reaches_the_log(
    sink: CollectingSink, log_stream: StringIO
) -> None:
    """The whole point: a prompt of Vokara is PII from beginning to end."""
    answer = ProviderAnswer(
        value=f"{CANDIDATE_NAME} · {CANDIDATE_PHONE} · {ANSWER_TEXT}",
        usage=TokenUsage(input_tokens=1, output_tokens=1),
    )

    await _trace_call(answer)()

    emitted = log_stream.getvalue()
    for secret in (CANDIDATE_NAME, CANDIDATE_PHONE, ANSWER_TEXT, INCOMPLETE_CV_SAMPLE.strip()):
        assert secret not in emitted

    (trace,) = sink.traces
    assert CANDIDATE_NAME not in json.dumps(vars(trace), default=str)


async def test_a_failed_call_is_traced_too_and_still_raises(sink: CollectingSink) -> None:
    """A failure costs latency and tokens, and it is the one being waited on."""
    with pytest.raises(ConnectionError):
        await _trace_call(ConnectionError(CANDIDATE_PHONE))()

    (trace,) = sink.traces
    assert trace.outcome == OUTCOME_PROVIDER_ERROR


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (TimeoutError(), OUTCOME_TIMEOUT),
        (ConnectionError(), OUTCOME_PROVIDER_ERROR),
    ],
)
async def test_the_outcome_says_how_the_attempt_ended(
    error: Exception, expected: str, sink: CollectingSink
) -> None:
    with pytest.raises(type(error)):
        await _trace_call(error)()

    assert sink.traces[0].outcome == expected


async def test_an_answer_that_does_not_validate_is_a_schema_error(sink: CollectingSink) -> None:
    with pytest.raises(Exception, match="validation error"):
        await _trace_call(_validation_error())()

    assert sink.traces[0].outcome == OUTCOME_SCHEMA_ERROR


def _validation_error() -> Exception:
    try:
        PreflightExtraction(years_of_experience="not a number")  # type: ignore[arg-type]
    except Exception as error:
        return error
    raise AssertionError("the schema accepted something it should not have")


async def test_every_attempt_of_a_retried_call_gets_its_own_row(sink: CollectingSink) -> None:
    """Three retries are three calls the user pays for (art. VIII)."""
    chat = _FakeChat(failures=2)
    adapter = GoogleStructuredOutput(
        model=MODEL,
        credential=SecretStr("a-local-credential"),
        chat_factory=lambda *_: chat,
        sleep=_no_sleep,
    )

    await adapter.generate(
        schema=PreflightExtraction,
        prompt=INCOMPLETE_CV_SAMPLE,
        purpose="extraction",
        prompt_version=PREFLIGHT_PROMPT_VERSION,
        trace_context=TraceContext(capability=Capability.GENERATION),
    )

    assert [trace.attempt for trace in sink.traces] == [1, 2, 3]
    assert [trace.outcome for trace in sink.traces] == [
        OUTCOME_PROVIDER_ERROR,
        OUTCOME_PROVIDER_ERROR,
        OUTCOME_OK,
    ]


async def test_a_sink_that_breaks_never_breaks_the_call(log_stream: StringIO) -> None:
    """Losing a trace is bad; losing someone's CV parse over it is worse."""

    class BrokenSink:
        def record(self, trace: LlmCallTrace) -> None:
            raise RuntimeError("the disk is full")

    register_trace_sink(BrokenSink())
    try:
        answer = await _trace_call(ProviderAnswer(value=ANSWER_TEXT))()
    finally:
        clear_trace_sinks()

    assert answer == ANSWER_TEXT
    assert "llm_trace_sink_failed" in log_stream.getvalue()


def test_the_sink_is_a_protocol_so_the_adapter_never_imports_the_database() -> None:
    """Art. II: `adapters/` may not reach into `db/`, and it does not."""
    assert isinstance(CollectingSink(), LlmCallTraceSink)

    import app.adapters.llm.tracing as tracing

    source = tracing.__file__
    with open(source, encoding="utf-8") as handle:
        assert "app.db" not in handle.read()


async def _no_sleep(seconds: float) -> None:
    del seconds


class _FakeChat:
    """Fails the first `failures` attempts, then answers."""

    def __init__(self, *, failures: int) -> None:
        self.failures = failures

    def with_structured_output(self, schema: type, include_raw: bool = False) -> _FakeChat:
        del schema, include_raw
        return self

    async def ainvoke(self, prompt: str) -> Any:  # noqa: ANN401
        del prompt
        if self.failures:
            self.failures -= 1
            raise ConnectionError("provider unreachable")
        return {"raw": None, "parsed": PreflightExtraction(), "parsing_error": None}
