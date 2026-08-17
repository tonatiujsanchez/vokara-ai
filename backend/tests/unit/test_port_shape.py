"""The shape of the ports is the contract; this test is what makes it binding.

Every rule checked here is an absence, and absences are what code review misses.
A `temperature` added «just for this provider», a `base_url` promoted into the
signature to save a factory, an `api_key` argument that quietly assumes there is
one: each would pass any functional test and each would close the door on the
second implementation (ADR-011 decision 5, research R-25).
"""

from __future__ import annotations

import inspect
from collections.abc import Sequence
from typing import get_type_hints

import pytest

from app.adapters.llm.base import (
    CapabilityProbePort,
    EmbeddingsPort,
    ProviderCallError,
    ProviderFailure,
    StructuredOutputPort,
    TraceContext,
)
from app.domain.capability import Capability

# Not in a signature, not in a default, not anywhere (research R-25).
SAMPLING_PARAMETERS = ("temperature", "top_p", "top_k")

# Configuration of the implementation, resolved in factory.py from Settings.
IMPLEMENTATION_CONFIGURATION = ("api_key", "credential", "base_url", "endpoint", "url")


def test_generate_takes_exactly_the_arguments_of_the_contract() -> None:
    parameters = inspect.signature(StructuredOutputPort.generate).parameters
    assert list(parameters) == [
        "self",
        "schema",
        "prompt",
        "purpose",
        "prompt_version",
        "trace_context",
    ]


def test_generate_is_keyword_only_so_the_call_site_reads_as_the_contract() -> None:
    parameters = inspect.signature(StructuredOutputPort.generate).parameters
    positional = [
        name
        for name, parameter in parameters.items()
        if name != "self" and parameter.kind is not inspect.Parameter.KEYWORD_ONLY
    ]
    assert not positional


def test_generate_is_generic_over_the_schema_it_is_given() -> None:
    """The answer comes back as the type asked for, not as a dict to trust."""
    signature = inspect.signature(StructuredOutputPort.generate)
    assert signature.return_annotation == "T"
    assert str(signature.parameters["schema"].annotation) == "type[T]"


@pytest.mark.parametrize("forbidden", SAMPLING_PARAMETERS)
def test_no_sampling_parameter_reaches_the_port(forbidden: str) -> None:
    source = inspect.getsource(StructuredOutputPort)
    assert forbidden not in source


@pytest.mark.parametrize("forbidden", IMPLEMENTATION_CONFIGURATION)
def test_no_credential_and_no_endpoint_in_the_signatures(forbidden: str) -> None:
    """Nothing here may assume there is an API key or where the endpoint is."""
    for port in (StructuredOutputPort, EmbeddingsPort, CapabilityProbePort):
        for _, member in inspect.getmembers(port, callable):
            try:
                parameters = inspect.signature(member).parameters
            except (TypeError, ValueError):  # pragma: no cover — builtins
                continue
            assert not [name for name in parameters if forbidden in name.lower()]


def test_the_embeddings_port_exposes_the_two_facts_a_vector_is_stored_with() -> None:
    """`embedding_model` and `embedding_dim` per vector is ADR-003, not a detail."""
    assert isinstance(inspect.getattr_static(EmbeddingsPort, "model_name"), property)
    assert isinstance(inspect.getattr_static(EmbeddingsPort, "dimensions"), property)

    signature = inspect.signature(EmbeddingsPort.embed_texts)
    assert list(signature.parameters) == ["self", "texts"]
    assert get_type_hints(EmbeddingsPort.embed_texts)["texts"] == Sequence[str]


def test_both_calls_are_asynchronous() -> None:
    assert inspect.iscoroutinefunction(StructuredOutputPort.generate)
    assert inspect.iscoroutinefunction(EmbeddingsPort.embed_texts)
    assert inspect.iscoroutinefunction(CapabilityProbePort.probe)


def test_the_probe_returns_a_typed_variant_and_never_a_raw_error() -> None:
    signature = inspect.signature(CapabilityProbePort.probe)
    assert list(signature.parameters) == ["self"]
    assert signature.return_annotation == "PreflightAttempt"
    assert isinstance(inspect.getattr_static(CapabilityProbePort, "capability"), property)


def test_a_classified_failure_carries_no_text_from_the_provider() -> None:
    """FR-008: the provider's message can echo the key back. It stops here."""
    error = ProviderCallError(ProviderFailure.CREDENTIAL_REJECTED, model="a-configured-model")

    assert error.failure is ProviderFailure.CREDENTIAL_REJECTED
    assert str(error) == "provider call failed: credential_rejected"
    assert not [name for name in vars(error) if "response" in name or "message" in name]


def test_the_classification_covers_every_way_a_call_can_fail() -> None:
    """Five failures, five messages. R-23: collapsing them loses FR-007."""
    assert {failure.value for failure in ProviderFailure} == {
        "credential_rejected",
        "quota_exceeded",
        "unreachable",
        "model_not_available",
        "schema_violation",
    }


def test_the_trace_context_has_nowhere_to_put_content() -> None:
    """No prompt, no document, no response: art. V leaves no field for them."""
    fields = get_type_hints(TraceContext)
    assert set(fields) == {"capability", "parse_job_id"}
    assert fields["capability"] is Capability
