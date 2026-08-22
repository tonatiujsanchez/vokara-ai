"""The adapter classifies, retries and never lets a raw provider error escape.

Nothing here touches the network: the client is injected, so what is under test
is the only thing that is ours — how a provider failure becomes one of the four
variants, and what gets retried before giving up (contracts/llm-extraction.md,
research R-23).
"""

from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel, SecretStr

from app.adapters.llm.base import ProviderCallError, ProviderFailure, TraceContext
from app.adapters.llm.google import (
    BACKOFF_BASE_SECONDS,
    MAX_ATTEMPTS,
    GoogleEmbeddings,
    GoogleStructuredOutput,
    classify,
)
from app.adapters.llm.schemas import PreflightExtraction
from app.domain.capability import (
    Capability,
    CapabilityUnverified,
    CredentialRejected,
    ProviderUnreachable,
    QuotaExceeded,
    Verified,
)

MODEL = "a-configured-generation-model"
EMBEDDINGS_MODEL = "a-configured-embeddings-model"


class ProviderApiError(Exception):
    """Shaped like the SDK's error: a status code and a message."""

    def __init__(self, code: int, message: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class FakeRawMessage:
    """The provider's message, with the token counts the trace reads off it."""

    def __init__(self, input_tokens: int = 11, output_tokens: int = 22) -> None:
        self.usage_metadata = {"input_tokens": input_tokens, "output_tokens": output_tokens}
        # Present precisely so the tests can prove nothing reads it.
        self.content = "El CV completo de María López, que jamás debe salir de aquí."


class FakeChat:
    """Stands in for the chat client, returning or raising what a test needs."""

    def __init__(self, *, answers: list[object]) -> None:
        self.answers = answers
        self.calls = 0
        self.include_raw: bool | None = None
        self.last_payload: str | list[dict[str, str]] | None = None

    def with_structured_output(
        self, schema: type[BaseModel], include_raw: bool = False
    ) -> FakeChat:
        self.schema = schema
        self.include_raw = include_raw
        return self

    async def ainvoke(self, prompt: str | list[dict[str, str]]) -> object:
        self.last_payload = prompt
        self.calls += 1
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        if isinstance(answer, dict):
            return answer
        return {"raw": FakeRawMessage(), "parsed": answer, "parsing_error": None}


class FakeEmbeddings:
    def __init__(self, *, answers: list[object]) -> None:
        self.answers = answers
        self.calls = 0

    async def aembed_documents(self, texts: list[str]) -> object:
        del texts
        self.calls += 1
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer


def _generation(*answers: object, slept: list[float] | None = None) -> GoogleStructuredOutput:
    chat = FakeChat(answers=list(answers))

    async def sleep(seconds: float) -> None:
        (slept if slept is not None else []).append(seconds)

    adapter = GoogleStructuredOutput(
        model=MODEL,
        credential=SecretStr("a-local-credential"),
        chat_factory=lambda *_: chat,
        sleep=sleep,
    )
    adapter.fake_chat = chat  # type: ignore[attr-defined]
    return adapter


def _embeddings(*answers: object) -> GoogleEmbeddings:
    client = FakeEmbeddings(answers=list(answers))

    async def sleep(seconds: float) -> None:
        del seconds

    adapter = GoogleEmbeddings(
        model=EMBEDDINGS_MODEL,
        dimensions=768,
        credential=SecretStr("a-local-credential"),
        embeddings_factory=lambda *_: client,
        sleep=sleep,
    )
    adapter.fake_client = client  # type: ignore[attr-defined]
    return adapter


def _honest_extraction() -> PreflightExtraction:
    """What the sample CV says, with every hole left alone."""
    return PreflightExtraction(full_name="María López Hernández", skills=["Python"])


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ProviderApiError(401), ProviderFailure.CREDENTIAL_REJECTED),
        (ProviderApiError(403), ProviderFailure.CREDENTIAL_REJECTED),
        (ProviderApiError(429), ProviderFailure.QUOTA_EXCEEDED),
        (ProviderApiError(404), ProviderFailure.MODEL_NOT_AVAILABLE),
        (ProviderApiError(500), ProviderFailure.UNREACHABLE),
        (ProviderApiError(503), ProviderFailure.UNREACHABLE),
        (ConnectionError("dns"), ProviderFailure.UNREACHABLE),
        (TimeoutError(), ProviderFailure.UNREACHABLE),
        (RuntimeError("something nobody has seen"), ProviderFailure.UNREACHABLE),
    ],
)
def test_every_provider_error_lands_on_one_classification(
    error: Exception, expected: ProviderFailure
) -> None:
    assert classify(error) is expected


def test_a_bad_request_is_only_called_a_bad_key_when_it_says_so() -> None:
    """Both are 400 here, and confusing them costs the user a regenerated key."""
    assert (
        classify(ProviderApiError(400, "API key not valid. Please pass a valid API key."))
        is ProviderFailure.CREDENTIAL_REJECTED
    )
    assert (
        classify(ProviderApiError(400, "Request contains an invalid argument."))
        is ProviderFailure.UNREACHABLE
    )


async def test_a_transient_failure_is_retried_with_exponential_backoff() -> None:
    slept: list[float] = []
    adapter = _generation(
        ProviderApiError(503), ProviderApiError(503), _honest_extraction(), slept=slept
    )

    answer = await adapter.generate(
        schema=PreflightExtraction,
        prompt="irrelevant",
        purpose="preflight",
        prompt_version="preflight_v1",
        trace_context=TraceContext(capability=Capability.GENERATION),
    )

    assert isinstance(answer, PreflightExtraction)
    assert slept == [BACKOFF_BASE_SECONDS, BACKOFF_BASE_SECONDS * 2]


async def test_it_gives_up_after_three_attempts() -> None:
    adapter = _generation(*[ProviderApiError(503) for _ in range(MAX_ATTEMPTS)])

    with pytest.raises(ProviderCallError) as raised:
        await adapter.generate(
            schema=PreflightExtraction,
            prompt="irrelevant",
            purpose="extraction",
            prompt_version="preflight_v1",
            trace_context=TraceContext(capability=Capability.GENERATION),
        )

    assert raised.value.failure is ProviderFailure.UNREACHABLE
    assert adapter.fake_chat.calls == MAX_ATTEMPTS  # type: ignore[attr-defined]


async def test_a_rejected_credential_is_not_retried() -> None:
    """Three calls to be told the same thing spend quota for nothing."""
    adapter = _generation(ProviderApiError(401))

    outcome = await adapter.probe()

    assert isinstance(outcome, CredentialRejected)
    assert adapter.fake_chat.calls == 1  # type: ignore[attr-defined]


async def test_a_retired_model_travels_as_an_error_and_not_as_a_verdict() -> None:
    """It says nothing about the credential or the capability (errors.md)."""
    adapter = _generation(ProviderApiError(404))

    with pytest.raises(ProviderCallError) as raised:
        await adapter.probe()

    assert raised.value.failure is ProviderFailure.MODEL_NOT_AVAILABLE
    assert raised.value.model == MODEL


async def test_an_exhausted_quota_says_the_key_works() -> None:
    adapter = _generation(*[ProviderApiError(429) for _ in range(MAX_ATTEMPTS)])

    outcome = await adapter.probe()

    assert isinstance(outcome, QuotaExceeded)
    assert outcome.allows_progress is False


async def test_no_connection_is_not_a_wrong_key() -> None:
    adapter = _generation(*[ConnectionError("dns") for _ in range(MAX_ATTEMPTS)])

    outcome = await adapter.probe()

    assert isinstance(outcome, ProviderUnreachable)


async def test_a_provider_that_invents_values_is_not_verified() -> None:
    """Art. IV: the parse worked perfectly and the answer is still unusable."""
    inventing = PreflightExtraction(
        full_name="María López Hernández",
        phone="+52 55 1234 5678",
        years_of_experience=5,
    )
    adapter = _generation(inventing)

    outcome = await adapter.probe()

    assert isinstance(outcome, CapabilityUnverified)
    assert len(outcome.affected_features_es) == 2
    assert all(reason.endswith(".") for reason in outcome.affected_features_es)


async def test_an_honest_answer_verifies_the_generation_capability() -> None:
    adapter = _generation(_honest_extraction())

    outcome = await adapter.probe()

    assert outcome == Verified(capability=Capability.GENERATION, model=MODEL)


async def test_the_embeddings_probe_records_the_dimension_it_observed() -> None:
    adapter = _embeddings([[0.1] * 768])

    outcome = await adapter.probe()

    assert isinstance(outcome, Verified)
    assert outcome.capability is Capability.EMBEDDINGS
    assert outcome.embedding_dim == 768


async def test_a_dimension_other_than_the_one_requested_is_recorded_as_it_came() -> None:
    """That number ends up beside every vector; guessing it is a corruption."""
    adapter = _embeddings([[0.1] * 3072])

    outcome = await adapter.probe()

    assert isinstance(outcome, Verified)
    assert outcome.embedding_dim == 3072
    assert adapter.dimensions == 768


async def test_an_empty_vector_is_a_capability_that_did_not_hold() -> None:
    adapter = _embeddings([[]])

    outcome = await adapter.probe()

    assert isinstance(outcome, CapabilityUnverified)


async def test_the_embeddings_probe_classifies_its_own_errors_too() -> None:
    adapter = _embeddings(ProviderApiError(401))

    outcome = await adapter.probe()

    assert isinstance(outcome, CredentialRejected)
    assert outcome.capability is Capability.EMBEDDINGS


async def test_an_answer_with_nothing_parsed_is_retried_and_then_unverified() -> None:
    """The provider replied; the structured output is what did not hold."""
    unparsed = {"raw": FakeRawMessage(), "parsed": None, "parsing_error": None}
    adapter = _generation(*[dict(unparsed) for _ in range(MAX_ATTEMPTS)])

    outcome = await adapter.probe()

    assert isinstance(outcome, CapabilityUnverified)
    assert adapter.fake_chat.calls == MAX_ATTEMPTS  # type: ignore[attr-defined]


async def test_the_raw_message_is_requested_so_tokens_can_be_traced() -> None:
    """Art. VIII asks for cost; without include_raw there are no token counts."""
    adapter = _generation(_honest_extraction())

    await adapter.probe()

    assert adapter.fake_chat.include_raw is True  # type: ignore[attr-defined]


def test_the_two_capabilities_are_two_objects_with_two_credentials() -> None:
    """FR-004: choosing one provider must not decide the other."""
    assert GoogleStructuredOutput.capability is Capability.GENERATION
    assert GoogleEmbeddings.capability is Capability.EMBEDDINGS


def test_no_sampling_parameter_is_ever_sent() -> None:
    """Deprecated in this provider's current models, and never load-bearing."""
    import inspect

    from app.adapters.llm import google

    source = inspect.getsource(google._build_chat)
    assert "temperature" not in source
    assert "top_p" not in source
    assert "top_k" not in source


def test_the_critical_rule_travels_as_a_system_turn_and_not_as_content() -> None:
    """The divergence that made the ADR-011 row uncertifiable (art. VI).

    The empirical verification behind that row always sent «si un dato NO
    aparece… el campo DEBE quedar en null» as a system instruction. The product
    concatenated it into the user message, so the two ran different tests on the
    same model and only one of them was written down.
    """
    from app.adapters.llm.prompts.preflight_v2 import (
        INCOMPLETE_CV_SAMPLE,
        PREFLIGHT_INSTRUCTIONS_ES,
    )

    adapter = _generation(_honest_extraction())
    asyncio.run(adapter.probe())

    payload = adapter.fake_chat.last_payload  # type: ignore[attr-defined]
    assert payload == [
        {"role": "system", "content": PREFLIGHT_INSTRUCTIONS_ES},
        {"role": "user", "content": INCOMPLETE_CV_SAMPLE},
    ]


def test_a_caller_with_no_rule_to_impose_sends_a_bare_prompt() -> None:
    """No empty system turn is invented for callers that pass no instructions."""
    adapter = _generation(_honest_extraction())

    asyncio.run(
        adapter.generate(
            schema=PreflightExtraction,
            prompt="solo el material",
            purpose="extraction",
            prompt_version="whatever_v1",
            trace_context=TraceContext(capability=Capability.GENERATION),
        )
    )

    assert adapter.fake_chat.last_payload == "solo el material"  # type: ignore[attr-defined]

