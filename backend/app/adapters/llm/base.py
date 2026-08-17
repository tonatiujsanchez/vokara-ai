"""The ports every LLM provider implements (art. II, art. XI, ADR-011).

Three rules of shape are binding here, and each one exists to keep a future
decision cheap:

1. **The two ports are configured independently.** Generation and embeddings
   are two calls to two endpoints with two models; the only thing that ever
   tied them together was the convenient assumption that a user configures
   "one provider". Anthropic offers no embeddings, so that assumption costs
   whoever picks it the semantic matching (ADR-011, FR-004).

2. **`base_url` and the credential are not in the signatures.** They are
   configuration of the implementation, resolved in `factory.py` from
   `Settings`. What the rule buys is that no line of code assumes there *is* an
   API key or that the endpoint is the provider's: adding Ollama — or any
   OpenAI-compatible server — must be a new implementation of the port, never a
   refactor of the port. Ollama is not implemented in v1 (ADR-011 decision 5).

3. **No sampling parameters.** `temperature`, `top_p` and `top_k` are
   deprecated in Gemini 3.x and not every provider exposes them alike. The
   determinism art. III demands never rested on them: it rests on a typed
   schema at every boundary, flow decisions taken outside the model and rules
   that can be tested. A `temperature=0` in a port signature is the same bug as
   an `if provider == "..."` (research R-25, ADR-003).

The model name is not here either, for a reason of its own: it comes from
configuration with an environment override, so a provider retiring a model
cannot break an installation the user has not updated (ADR-011).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel

from app.domain.capability import Capability, PreflightAttempt

# Why the model was called. It lands in `llm_call_logs` so cost can later be
# read per stage of the pipeline (art. VIII, FR-046).
type Purpose = Literal["classification", "extraction", "preflight"]


@dataclass(frozen=True)
class TraceContext:
    """Everything a trace may carry, which is to say: no content at all.

    There is no field for the prompt, the document or the response, and that
    absence is the design. A trace is metadata; anything else would put the CV
    in a log line (art. V, FR-046, research R-13).
    """

    capability: Capability
    parse_job_id: UUID | None = None


@runtime_checkable
class StructuredOutputPort(Protocol):
    """A typed answer from a model, or an error. Never free text (art. III)."""

    async def generate[T: BaseModel](
        self,
        *,
        schema: type[T],
        prompt: str,
        purpose: Purpose,
        prompt_version: str,
        trace_context: TraceContext,
    ) -> T: ...


@runtime_checkable
class EmbeddingsPort(Protocol):
    """Vectors, and the two facts that make a change of provider survivable.

    `model_name` and `dimensions` are persisted next to every vector so that
    switching provider means re-embedding, never losing the profile (art. II,
    ADR-003). No vector is persisted in this feature (research R-12); the port
    exists because its preflight is a functional requirement.
    """

    @property
    def model_name(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]: ...


@runtime_checkable
class CapabilityProbePort(Protocol):
    """Verifying a capability, with the classification already done.

    The service must never inspect a raw provider error: only the adapter knows
    what a 401 or a 429 looks like at its provider, so the classification lives
    here and what crosses the boundary is an already typed variant
    (contracts/llm-extraction.md, research R-23).

    One probe per capability, because generation and embeddings are configured
    independently: probing one says nothing about the other (FR-004).
    """

    @property
    def capability(self) -> Capability: ...

    async def probe(self) -> PreflightAttempt: ...


class ProviderFailure(StrEnum):
    """Why a real call failed, classified by the adapter that made it.

    The preflight turns these into the variants of FR-007; the parsing pipeline
    turns them into the error codes of contracts/errors.md. Both read the same
    classification, which is the point: the service never inspects a raw error,
    and there is exactly one place per provider that knows what a 401 looks
    like there (research R-23).
    """

    CREDENTIAL_REJECTED = "credential_rejected"
    QUOTA_EXCEEDED = "quota_exceeded"
    # Also the default for anything unrecognised: «no pudimos verificar» is the
    # only honest thing to say about an error nobody classified, and saying
    # «tu llave es incorrecta» about a working key sends the user to regenerate
    # it for nothing (research R-23).
    UNREACHABLE = "unreachable"
    MODEL_NOT_AVAILABLE = "model_not_available"
    SCHEMA_VIOLATION = "schema_violation"


class ProviderCallError(Exception):
    """A classified failure. Deliberately carries no text from the provider.

    The provider's message can echo back the key that was sent, or a fragment
    of the prompt, so it stops here: what crosses the boundary is the
    classification and the configured model, never the raw payload (FR-008,
    art. V).
    """

    def __init__(self, failure: ProviderFailure, *, model: str) -> None:
        super().__init__(f"provider call failed: {failure.value}")
        self.failure = failure
        self.model = model
