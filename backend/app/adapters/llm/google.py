"""The only implementation of the ports in v1 (ADR-011).

It is the only one because it is the only provider whose empirical verification
row is complete, and FR-009 forbids offering what has not been verified. Two
independent classes rather than one object serving both ports, because
generation and embeddings are configured independently: one credential, one
model and one preflight each (FR-004).

**The classification of provider errors lives here and nowhere else.** Only the
adapter knows what a 401 or a 429 looks like at its provider; what crosses the
boundary is an already typed variant, and no service ever inspects a raw error
(contracts/llm-extraction.md, research R-23).

**No sampling parameters are sent.** `temperature`, `top_p` and `top_k` are
deprecated in Gemini 3.x and were never what made the pipeline deterministic:
that comes from the typed schema at every boundary, flow decisions taken
outside the model and rules that can be tested (research R-25, ADR-003).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from pydantic import BaseModel, SecretStr, ValidationError

from app.adapters.llm.base import (
    ProviderCallError,
    ProviderFailure,
    Purpose,
    TraceContext,
)
from app.adapters.llm.prompts.preflight_v2 import (
    EMBEDDINGS_PROBE_TEXT,
    EMBEDDINGS_PROBE_VERSION,
    PREFLIGHT_INSTRUCTIONS_ES,
    PREFLIGHT_PROMPT_VERSION,
    build_preflight_prompt,
)
from app.adapters.llm.schemas import PreflightExtraction, unmet_null_expectations
from app.adapters.llm.tracing import (
    NO_USAGE,
    ProviderAnswer,
    traced,
    usage_from_provider_metadata,
)
from app.core.logging import get_logger
from app.domain.capability import (
    Capability,
    CapabilityUnverified,
    CredentialRejected,
    PreflightAttempt,
    ProviderUnreachable,
    QuotaExceeded,
    Verified,
)

logger = get_logger(__name__)

# Three attempts in total, not three on top of the first. Every attempt is a
# call the user pays for and a second of a spinner they are watching, and the
# failures worth retrying — a dropped connection, a 429, an answer that does not
# validate — rarely need a fourth try to show their hand.
MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 1.0

# Retrying a rejected credential or a retired model just spends the user's
# quota to reach the same answer.
RETRYABLE: frozenset[ProviderFailure] = frozenset(
    {
        ProviderFailure.UNREACHABLE,
        ProviderFailure.QUOTA_EXCEEDED,
        ProviderFailure.SCHEMA_VIOLATION,
    }
)

# HTTP status as this provider reports it, mapped onto the classification.
# 400 is deliberately absent: this provider answers a bad key with a 400
# INVALID_ARGUMENT, but so does a malformed request, and calling the second one
# «tu llave es incorrecta» sends the user to regenerate a key that works.
_STATUS_TO_FAILURE: dict[int, ProviderFailure] = {
    401: ProviderFailure.CREDENTIAL_REJECTED,
    403: ProviderFailure.CREDENTIAL_REJECTED,
    404: ProviderFailure.MODEL_NOT_AVAILABLE,
    429: ProviderFailure.QUOTA_EXCEEDED,
}

# Read in memory to tell those two 400s apart, and discarded immediately: the
# provider's text may quote the key back and never reaches a log, a trace or a
# response (art. V, FR-008).
_REJECTED_KEY_MARKERS = ("api key", "api_key", "api-key", "credential")


type Sleeper = Callable[[float], Awaitable[None]]


class StructuredOutputMissingError(Exception):
    """The provider answered, and the answer had no parsed object in it.

    Not a transport failure and not an invented value: the capability simply
    did not hold on this attempt, which is why it is retried and, if it
    survives the retries, reported as unverified rather than as an error.
    """


def classify(error: BaseException) -> ProviderFailure:
    """Turn a provider error into the one classification the rest of the app sees.

    An answer that does not validate against the schema is a failure of the
    capability, not of the transport: `with_structured_output` raises it as a
    validation error and it is retried like a network blip, but if it survives
    the retries it means the provider does not reliably produce the structured
    output this pipeline needs.

    Anything unrecognised falls to `UNREACHABLE`, which reads as «no pudimos
    verificar». Guessing «your key is wrong» about a key that works is the one
    mistake with a concrete cost: the user goes and regenerates it (R-23).
    """
    if isinstance(error, ValidationError | StructuredOutputMissingError):
        return ProviderFailure.SCHEMA_VIOLATION
    if type(error).__name__ == "OutputParserException":
        return ProviderFailure.SCHEMA_VIOLATION

    status = getattr(error, "code", None) or getattr(error, "status_code", None)
    if isinstance(status, int):
        if mapped := _STATUS_TO_FAILURE.get(status):
            return mapped
        if status == 400 and _mentions_the_credential(error):
            return ProviderFailure.CREDENTIAL_REJECTED
        # 5xx is the provider having a bad day, not the user having a bad key.
        return ProviderFailure.UNREACHABLE

    return ProviderFailure.UNREACHABLE


def _mentions_the_credential(error: BaseException) -> bool:
    text = str(getattr(error, "message", "") or "").lower()
    return any(marker in text for marker in _REJECTED_KEY_MARKERS)


async def _with_retries[T](
    call: Callable[[], Awaitable[ProviderAnswer[T]]],
    *,
    model: str,
    purpose: Purpose,
    prompt_version: str,
    trace_context: TraceContext,
    sleep: Sleeper,
) -> T:
    """Three attempts with exponential backoff, each one traced on its own.

    Each attempt is a call the user pays for, so each one gets its own row: the
    decorator records cost and latency for the failures too, which are the ones
    the diagnostics screen exists to explain (art. VIII, FR-046).

    Only the classification and the attempt number reach the log. Never the
    prompt, never the answer, never the credential (art. V).
    """
    last: ProviderFailure = ProviderFailure.UNREACHABLE

    for attempt in range(1, MAX_ATTEMPTS + 1):
        attempted = traced(
            capability=trace_context.capability,
            purpose=purpose,
            model=model,
            prompt_version=prompt_version,
            attempt=attempt,
            parse_job_id=trace_context.parse_job_id,
        )(call)

        try:
            return await attempted()
        except ProviderCallError:
            raise
        except Exception as error:
            last = classify(error)
            logger.warning(
                "llm_call_failed",
                purpose=purpose,
                model=model,
                attempt=attempt,
                failure=last.value,
                error_type=type(error).__name__,
            )
            if last not in RETRYABLE or attempt == MAX_ATTEMPTS:
                raise ProviderCallError(last, model=model) from None
            await sleep(BACKOFF_BASE_SECONDS * 2 ** (attempt - 1))

    raise ProviderCallError(last, model=model)  # pragma: no cover — loop always returns or raises


def _unwrap[T: BaseModel](answer: Any, schema: type[T]) -> ProviderAnswer[T]:  # noqa: ANN401
    """The parsed object and its token count, out of the provider's payload.

    `include_raw` is what makes the token counts available at all, and reading
    exactly two integers out of the object that also holds the answer text is
    the whole of the interaction with it (art. VIII, FR-046).
    """
    if not isinstance(answer, dict) or "parsed" not in answer:
        # A client that hands back the model directly: valid, just untraceable
        # for cost. Better a trace with zeros than an exception here.
        return ProviderAnswer(value=_validated(answer, schema), usage=NO_USAGE)

    if (parsing_error := answer.get("parsing_error")) is not None:
        if isinstance(parsing_error, BaseException):
            raise parsing_error
        raise StructuredOutputMissingError

    if (parsed := answer.get("parsed")) is None:
        raise StructuredOutputMissingError

    return ProviderAnswer(
        value=_validated(parsed, schema),
        usage=usage_from_provider_metadata(answer.get("raw")),
    )


def _validated[T: BaseModel](answer: Any, schema: type[T]) -> T:  # noqa: ANN401
    """Whatever came back leaves this module as the schema asked for (art. I)."""
    return answer if isinstance(answer, schema) else schema.model_validate(answer)


def _messages(instructions: str | None, prompt: str) -> str | list[dict[str, str]]:
    """The call payload: a system turn plus a user turn, or just the user turn.

    A bare string is still accepted so a caller with no rule to impose does not
    pay for an empty system message. When there is a rule, it travels in the
    turn models are trained to weigh most — which is where the empirical
    verification of ADR-011 always put it.
    """
    if instructions is None:
        return prompt
    return [
        {"role": "system", "content": instructions},
        {"role": "user", "content": prompt},
    ]


def _build_chat(model: str, credential: SecretStr | None, base_url: str | None) -> Any:  # noqa: ANN401
    """Late import so the SDK is not a cost paid by every process that imports us."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    options: dict[str, Any] = {"model": model}
    # Both stay optional so nothing here assumes there is a key or that the
    # endpoint is the provider's (ADR-011 decision 5).
    if credential is not None:
        options["google_api_key"] = credential.get_secret_value()
    if base_url is not None:
        options["base_url"] = base_url
    return ChatGoogleGenerativeAI(**options)


def _build_embeddings(
    model: str, credential: SecretStr | None, base_url: str | None, dimensions: int
) -> Any:  # noqa: ANN401
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    options: dict[str, Any] = {"model": model, "output_dimensionality": dimensions}
    if credential is not None:
        options["google_api_key"] = credential.get_secret_value()
    if base_url is not None:
        options["base_url"] = base_url
    return GoogleGenerativeAIEmbeddings(**options)


class GoogleStructuredOutput:
    """`StructuredOutputPort` and the preflight of the generation capability."""

    capability = Capability.GENERATION

    def __init__(
        self,
        *,
        model: str,
        credential: SecretStr | None = None,
        base_url: str | None = None,
        chat_factory: Callable[[str, SecretStr | None, str | None], Any] = _build_chat,
        sleep: Sleeper = asyncio.sleep,
    ) -> None:
        self._model = model
        self._credential = credential
        self._base_url = base_url
        self._chat_factory = chat_factory
        self._sleep = sleep
        self._chat: Any | None = None

    @property
    def model_name(self) -> str:
        return self._model

    def _client(self) -> Any:  # noqa: ANN401
        if self._chat is None:
            self._chat = self._chat_factory(self._model, self._credential, self._base_url)
        return self._chat

    async def generate[T: BaseModel](
        self,
        *,
        schema: type[T],
        prompt: str,
        purpose: Purpose,
        prompt_version: str,
        trace_context: TraceContext,
        instructions: str | None = None,
    ) -> T:
        async def call() -> ProviderAnswer[T]:
            structured = self._client().with_structured_output(schema, include_raw=True)
            return _unwrap(await structured.ainvoke(_messages(instructions, prompt)), schema)

        return await _with_retries(
            call,
            model=self._model,
            purpose=purpose,
            prompt_version=prompt_version,
            trace_context=trace_context,
            sleep=self._sleep,
        )

    async def probe(self) -> PreflightAttempt:
        """FR-006: run at save time, and it measures honesty, not parsing.

        A model that returns perfectly shaped output while inventing a phone
        number the CV never had passes any structural check and still produces
        claims with nothing behind them. That is the failure art. IV exists to
        stop, and the reason the approval criterion is the `null`s.
        """
        try:
            extraction = await self.generate(
                schema=PreflightExtraction,
                instructions=PREFLIGHT_INSTRUCTIONS_ES,
                prompt=build_preflight_prompt(),
                purpose="preflight",
                prompt_version=PREFLIGHT_PROMPT_VERSION,
                trace_context=TraceContext(capability=self.capability),
            )
        except ProviderCallError as error:
            return _as_attempt(error, capability=self.capability)

        if invented := unmet_null_expectations(extraction):
            return CapabilityUnverified(
                capability=self.capability,
                model=self._model,
                affected_features_es=tuple(failure.description_es for failure in invented),
            )

        return Verified(capability=self.capability, model=self._model)


class GoogleEmbeddings:
    """`EmbeddingsPort` and the preflight of the embeddings capability."""

    capability = Capability.EMBEDDINGS

    def __init__(
        self,
        *,
        model: str,
        dimensions: int,
        credential: SecretStr | None = None,
        base_url: str | None = None,
        embeddings_factory: Callable[
            [str, SecretStr | None, str | None, int], Any
        ] = _build_embeddings,
        sleep: Sleeper = asyncio.sleep,
    ) -> None:
        self._model = model
        # MRL truncation from the 3072 the model returns by default: 768 saves
        # roughly four times the space in pgvector with no relevant loss of
        # quality (ADR-011, research R-12).
        self._dimensions = dimensions
        self._credential = credential
        self._base_url = base_url
        self._embeddings_factory = embeddings_factory
        self._sleep = sleep
        self._embeddings: Any | None = None

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def _client(self) -> Any:  # noqa: ANN401
        if self._embeddings is None:
            self._embeddings = self._embeddings_factory(
                self._model, self._credential, self._base_url, self._dimensions
            )
        return self._embeddings

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        async def call() -> ProviderAnswer[list[list[float]]]:
            vectors: list[list[float]] = await self._client().aembed_documents(list(texts))
            # This provider reports no token usage for embeddings; the trace
            # records zeros rather than a number nobody measured.
            return ProviderAnswer(value=vectors, usage=NO_USAGE)

        return await _with_retries(
            call,
            model=self._model,
            purpose="preflight",
            prompt_version=EMBEDDINGS_PROBE_VERSION,
            trace_context=TraceContext(capability=self.capability),
            sleep=self._sleep,
        )

    async def probe(self) -> PreflightAttempt:
        """A vector comes back, and the dimension it came back with is recorded.

        The observed dimension is what gets persisted, not the requested one: a
        provider that quietly returns something else must leave a trace of it,
        because that number ends up beside every vector (ADR-003).
        """
        try:
            vectors = await self.embed_texts([EMBEDDINGS_PROBE_TEXT])
        except ProviderCallError as error:
            return _as_attempt(error, capability=self.capability)

        if not vectors or not vectors[0]:
            return CapabilityUnverified(
                capability=self.capability,
                model=self._model,
                affected_features_es=("El proveedor no devolvió ningún vector.",),
            )

        return Verified(
            capability=self.capability,
            model=self._model,
            embedding_dim=len(vectors[0]),
        )


def _as_attempt(error: ProviderCallError, *, capability: Capability) -> PreflightAttempt:
    """The classified failure as the variant the wizard shows (FR-007).

    `MODEL_NOT_AVAILABLE` is not among them on purpose: a retired model is a
    configuration problem with its own actionable message, not a statement
    about the credential or the capability, so it keeps travelling as an error
    (contracts/errors.md).
    """
    match error.failure:
        case ProviderFailure.CREDENTIAL_REJECTED:
            return CredentialRejected(capability=capability, model=error.model)
        case ProviderFailure.QUOTA_EXCEEDED:
            return QuotaExceeded(capability=capability, model=error.model)
        case ProviderFailure.SCHEMA_VIOLATION:
            return CapabilityUnverified(
                capability=capability,
                model=error.model,
                affected_features_es=(
                    "El modelo no devolvió una respuesta con la estructura requerida.",
                ),
            )
        case ProviderFailure.UNREACHABLE:
            return ProviderUnreachable(capability=capability, model=error.model)
        case ProviderFailure.MODEL_NOT_AVAILABLE:
            raise error
