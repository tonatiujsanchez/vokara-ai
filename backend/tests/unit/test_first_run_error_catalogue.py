"""The first-run catalogue: every message actionable, none of them a leak.

Three rules of contracts/errors.md are checked here as properties of the whole
catalogue rather than as a habit of whoever writes the next endpoint:

1. no credential, complete or partial, and no technical trace (FR-008, FR-013);
2. no document content and no personal data (FR-045);
3. what happened, why, and the concrete next step — in local execution the
   message is all the support there is (roadmap §11.5).

The catalogue is enumerated by walking the subclasses of `DomainError`, so an
error added later is covered without anyone remembering to add it here.
"""

from __future__ import annotations

import pytest

from app.api.errors import error_response
from app.domain.capability import Capability, affected_features
from app.domain.errors import (
    DegradationAcknowledgementRequiredError,
    DisclosureAcknowledgementRequiredError,
    DomainError,
    EmailAppPasswordRejectedError,
    EmailLabelNotFoundError,
    EmailProviderUnreachableError,
    GenerationProviderRequiredError,
    ModelNotAvailableError,
    ProviderCredentialRejectedError,
    ProviderNotOfferedError,
    ProviderQuotaExceededError,
    ProviderUnreachableError,
)

A_KEY = "AIzaSyD-una-llave-real-tendria-esta-forma-39-chars"

FIRST_RUN_ERRORS: tuple[DomainError, ...] = (
    DisclosureAcknowledgementRequiredError(),
    ProviderCredentialRejectedError(console_url="https://ejemplo.invalid/consola"),
    ProviderQuotaExceededError(),
    ProviderUnreachableError(),
    ModelNotAvailableError(configured_model="un-modelo-retirado"),
    ProviderNotOfferedError(),
    DegradationAcknowledgementRequiredError(
        affected_features=[
            {"code": feature.code, "message": feature.message_es}
            for feature in affected_features(Capability.GENERATION)
        ]
    ),
    GenerationProviderRequiredError(),
    EmailAppPasswordRejectedError(oauth_docs_url="https://ejemplo.invalid/oauth"),
    EmailLabelNotFoundError(help_url="https://ejemplo.invalid/etiquetas"),
    EmailProviderUnreachableError(),
)

# Where a technical detail would show up if one ever slipped into a message.
TRACE_MARKERS: tuple[str, ...] = (
    "Traceback",
    "Exception",
    "Error:",
    "None",
    "null",
    "0x",
    "line ",
    'File "',
    "at 0x",
    "psycopg",
    "sqlalchemy",
    "httpx",
    "langchain",
    "401",
    "429",
    "503",
)


@pytest.mark.parametrize("error", FIRST_RUN_ERRORS, ids=lambda error: error.code)
def test_every_code_is_stable_english_and_every_message_is_spanish(error: DomainError) -> None:
    """Art. IX: the identifier travels in English, the text the user reads does not."""
    assert error.code.isupper()
    assert error.code.replace("_", "").isalpha()
    assert error.message
    assert error.message[0].isupper()


@pytest.mark.parametrize("error", FIRST_RUN_ERRORS, ids=lambda error: error.code)
def test_no_message_carries_a_credential_or_a_fragment_of_one(error: DomainError) -> None:
    """SC-013 measured where it is cheapest to break it: the error text."""
    body = bytes(error_response(error).body).decode("utf-8")

    assert A_KEY not in body
    for length in (8, 12, 20):
        assert A_KEY[:length] not in body


@pytest.mark.parametrize("error", FIRST_RUN_ERRORS, ids=lambda error: error.code)
def test_no_message_carries_a_technical_trace(error: DomainError) -> None:
    """A stack trace on screen is a product bug, not a debugging aid."""
    offending = [marker for marker in TRACE_MARKERS if marker in error.message]

    assert not offending, f"{error.code} leaks technical detail: {offending}"


@pytest.mark.parametrize("error", FIRST_RUN_ERRORS, ids=lambda error: error.code)
def test_every_message_says_what_to_do_next(error: DomainError) -> None:
    """Without a next step the message is incomplete (roadmap §11.5).

    Checked by looking for an instruction to the candidate — an imperative or a
    stated option — which is what distinguishes «qué pasó» from «qué hacer».
    """
    next_steps = (
        "Verifica",
        "Revisa",
        "Actualiza",
        "Créala",
        "Elige",
        "vuelve a intentarlo",
        "Inténtalo",
        "usa la vía OAuth",
        "necesitas",
        "necesitamos",
        "Puedes",
        "continúa",
    )

    assert any(step in error.message for step in next_steps), (
        f"{error.code} says what happened but not what to do (roadmap §11.5)"
    )


@pytest.mark.parametrize("error", FIRST_RUN_ERRORS, ids=lambda error: error.code)
def test_the_http_status_matches_the_catalogue(error: DomainError) -> None:
    expected = {
        "DISCLOSURE_ACKNOWLEDGEMENT_REQUIRED": 409,
        "PROVIDER_CREDENTIAL_REJECTED": 400,
        "PROVIDER_QUOTA_EXCEEDED": 429,
        "PROVIDER_UNREACHABLE": 503,
        "MODEL_NOT_AVAILABLE": 400,
        "PROVIDER_NOT_OFFERED": 422,
        "DEGRADATION_ACKNOWLEDGEMENT_REQUIRED": 409,
        "GENERATION_PROVIDER_REQUIRED": 409,
        "EMAIL_APP_PASSWORD_REJECTED": 400,
        "EMAIL_LABEL_NOT_FOUND": 422,
        "EMAIL_PROVIDER_UNREACHABLE": 503,
    }

    assert error.http_status == expected[error.code]


def test_a_rejected_quota_is_never_presented_as_a_rejected_credential() -> None:
    """The one confusion with a concrete cost: regenerating a key that works."""
    quota = ProviderQuotaExceededError()

    assert "válida" in quota.message
    assert "rechazó" not in quota.message


def test_the_degradation_error_enumerates_the_features_it_asks_to_accept() -> None:
    """SC-016: nothing is accepted before it is named."""
    error = DegradationAcknowledgementRequiredError(
        affected_features=[
            {"code": feature.code, "message": feature.message_es}
            for feature in affected_features(Capability.EMBEDDINGS)
        ]
    )

    assert error.details is not None
    assert error.details["affected_features"][0]["code"] == "SEMANTIC_MATCHING"


def test_the_missing_provider_error_is_about_generation_only() -> None:
    """FR-010: the absence of embeddings degrades, it never blocks."""
    assert "generación" in GenerationProviderRequiredError().message
    assert "embeddings" not in GenerationProviderRequiredError().message


def test_the_catalogue_covers_every_first_run_error_that_exists() -> None:
    """A code added to the module and forgotten here would test nothing."""
    declared = {error.code for error in FIRST_RUN_ERRORS}
    in_module = {
        subclass.code
        for subclass in DomainError.__subclasses__()
        if subclass.__module__ == "app.domain.errors"
    }

    assert in_module - declared == set(), f"Untested first-run errors: {in_module - declared}"
