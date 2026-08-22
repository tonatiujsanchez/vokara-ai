"""The error contract, checked where it can drift: between its three owners.

`contracts/errors.md` names the codes, `contracts/openapi.yaml` declares the
shape, and `app/domain/errors.py` implements both. Three documents saying the
same thing stay true only while something compares them, and the cost of them
disagreeing lands in the frontend: `contracts/errors.md` says the SPA branches
on `code` and on nothing else, so a code that exists in one place and not in
another is a branch that silently never fires.

This file is that comparison. It is also what makes the closed `ErrorCode`
enum worth having: the enum reaches `schema.d.ts` as a union of literals, and
these tests are what keep the union describing reality.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.api.errors import Error, error_response, error_responses
from app.domain.errors import DomainError, ErrorCode, ProviderQuotaExceededError
from app.openapi_export import build_openapi

CONTRACT = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "001-candidate-onboarding"
    / "contracts"
    / "openapi.yaml"
)


def domain_errors() -> set[type[DomainError]]:
    """Every error the module defines, base included.

    `DomainError` itself is one: it is what the fallback handler answers with,
    so INTERNAL_ERROR is a code the API really emits and not a placeholder.
    """
    return {DomainError} | {
        subclass
        for subclass in DomainError.__subclasses__()
        if subclass.__module__ == "app.domain.errors"
    }


def test_every_error_code_has_exactly_one_domain_error() -> None:
    """The correspondence the enum's docstring promises, enforced both ways.

    A code in the enum with no class is a code nothing can raise — dead weight
    the frontend would still have to handle. A class whose code is missing from
    the enum cannot exist at all: the annotation would not accept it.
    """
    implemented = {error.code for error in domain_errors()}

    assert implemented == set(ErrorCode), (
        f"only in the enum: {set(ErrorCode) - implemented} · "
        f"only in a class: {implemented - set(ErrorCode)}"
    )


def test_no_two_errors_share_a_code() -> None:
    """Two classes on one code make `code` ambiguous for the frontend."""
    codes = [error.code for error in domain_errors()]

    assert len(codes) == len(set(codes)), "a code is claimed by more than one error"


def test_the_design_contract_declares_the_same_closed_set() -> None:
    """`contracts/openapi.yaml` is the design source; it must say the same."""
    document: dict[str, Any] = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    declared = document["components"]["schemas"]["Error"]["properties"]["code"]["enum"]

    assert set(declared) == {code.value for code in ErrorCode}
    assert len(declared) == len(set(declared)), "the contract repeats a code"


def test_the_published_schema_is_the_one_the_design_contract_names() -> None:
    """The generated client must not learn a second name for the same body."""
    published = build_openapi()["components"]["schemas"]

    assert "Error" in published
    assert set(published["Error"]["properties"]) == {"code", "message", "details"}


def test_every_error_response_of_every_endpoint_refers_to_error() -> None:
    """Condition of art. I: the contract describes what the API really returns."""
    paths = build_openapi()["paths"]
    offending: list[str] = []

    for path, operations in paths.items():
        for verb, operation in operations.items():
            for status, response in operation["responses"].items():
                if not str(status).startswith(("4", "5")):
                    continue
                schema = response.get("content", {}).get("application/json", {}).get("schema", {})
                if schema.get("$ref", "").rsplit("/", 1)[-1] != "Error":
                    offending.append(f"{verb.upper()} {path} → {status}: {schema}")

    assert not offending, f"error responses outside the contract: {offending}"


def test_no_endpoint_still_publishes_fastapis_own_validation_body() -> None:
    """The 422 this application returns is the catalogue's, not FastAPI's.

    `register_error_handlers` intercepts `RequestValidationError` and answers
    `VALIDATION_ERROR`. While `HTTPValidationError` stayed in the schema the
    generated client typed a body that never arrives.
    """
    published = build_openapi()["components"]["schemas"]

    assert "HTTPValidationError" not in published
    assert "ValidationError" not in published


def test_every_endpoint_declares_the_internal_error_it_can_always_produce() -> None:
    """The fallback handler applies to every route, so every route declares it."""
    paths = build_openapi()["paths"]

    missing = [
        f"{verb.upper()} {path}"
        for path, operations in paths.items()
        for verb, operation in operations.items()
        if "500" not in operation["responses"]
    ]

    assert not missing, f"endpoints without a declared 500: {missing}"


def test_the_body_returned_validates_against_the_schema_declared() -> None:
    """Declared and returned are the same thing, checked on a real response."""
    response = error_response(ProviderQuotaExceededError())
    body = Error.model_validate_json(bytes(response.body))

    assert body.code is ErrorCode.PROVIDER_QUOTA_EXCEEDED
    assert response.status_code == ProviderQuotaExceededError.http_status


def test_the_helper_groups_by_status_and_always_adds_the_fallback() -> None:
    """Two errors on one status share a response; the 500 is never forgotten."""
    declared = error_responses(ProviderQuotaExceededError)

    assert set(declared) == {ProviderQuotaExceededError.http_status, DomainError.http_status}
    assert declared[ProviderQuotaExceededError.http_status]["model"] is Error
    assert (
        ErrorCode.PROVIDER_QUOTA_EXCEEDED.value
        in declared[ProviderQuotaExceededError.http_status]["description"]
    )
