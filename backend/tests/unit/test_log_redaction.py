"""No credential and no free text reaches a log line (art. V, FR-045, R-13)."""

from __future__ import annotations

import io
import json
from typing import Any

import pytest
from pydantic import SecretStr

from app.core.logging import (
    MAX_VALUE_CHARS,
    REDACTED,
    bind_parse_job_id,
    bind_request_id,
    clear_log_context,
    configure_logging,
    get_logger,
    redact_sensitive,
)


@pytest.fixture(autouse=True)
def _clear_context() -> None:
    clear_log_context()


def scrub(event: dict[str, Any]) -> dict[str, Any]:
    return dict(redact_sensitive(None, "info", event))


@pytest.mark.parametrize(
    "key",
    [
        "google_api_key",
        "GOOGLE_API_KEY",
        "apikey",
        "gmail_app_password",
        "password",
        "authorization",
        "credential_fingerprint",
        "access_token",
        "token",
        "key",
        "storage_key",
    ],
)
def test_sensitive_keys_are_dropped_by_name(key: str) -> None:
    assert scrub({key: "AIza-real-value"})[key] == REDACTED


def test_nested_structures_are_scrubbed() -> None:
    event = {
        "provider": {"name": "acme", "api_key": "AIza-real-value"},
        "attempts": [{"password": "hunter2"}, {"latency_ms": 12}],
    }

    result = scrub(event)

    assert result["provider"]["api_key"] == REDACTED
    assert result["provider"]["name"] == "acme"
    assert result["attempts"][0]["password"] == REDACTED
    assert result["attempts"][1]["latency_ms"] == 12


def test_secretstr_never_renders_its_value() -> None:
    result = scrub({"whatever": SecretStr("AIza-real-value")})

    assert result["whatever"] == REDACTED
    assert "AIza-real-value" not in json.dumps(result)


def test_free_text_is_truncated() -> None:
    cv_text = "Juan Perez, 55 5555 5555, " + ("experiencia laboral " * 200)

    result = scrub({"extracted_text": cv_text})

    assert len(result["extracted_text"]) <= MAX_VALUE_CHARS + len("…[truncado]")
    assert result["extracted_text"].endswith("…[truncado]")


def test_metadata_survives_untouched() -> None:
    """Redaction must not cost the observability art. VIII asks for."""
    event = {
        "model": "some-model",
        "prompt_version": "cv_extraction_v1",
        "input_tokens": 1200,
        "estimated_cost_usd": 0.0004,
        "latency_ms": 1540,
        "outcome": "ok",
    }

    assert scrub(event) == event


def test_request_id_and_parse_job_id_travel_with_the_line() -> None:
    stream = io.StringIO()
    configure_logging(stream=stream)
    bind_request_id("req-123")
    bind_parse_job_id("0192f3a0-0000-7000-8000-00000000abcd")

    get_logger("test").info("parse_started", google_api_key="AIza-real-value")

    line = json.loads(stream.getvalue().strip())
    assert line["request_id"] == "req-123"
    assert line["parse_job_id"] == "0192f3a0-0000-7000-8000-00000000abcd"
    assert line["google_api_key"] == REDACTED
    assert "AIza-real-value" not in stream.getvalue()
