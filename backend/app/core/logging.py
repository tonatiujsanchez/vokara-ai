"""Structured logging with redaction.

Article VIII asks for cost, latency and prompt version. Article V forbids
credentials and CV content anywhere near a log line. Both hold at once because
redaction is a processor in the chain, not a habit of whoever writes the next
log call (research R-13).

Two identifiers travel with every line so a run can be followed end to end:
`request_id` (HTTP) and `parse_job_id` (worker).
"""

from __future__ import annotations

import logging
import sys
from typing import Any, TextIO
from uuid import UUID

import structlog
from pydantic import SecretStr
from structlog.typing import EventDict, WrappedLogger

REDACTED = "***REDACTED***"

# A key whose name contains any of these never reaches the output, whatever it
# holds. Names, not values: matching on value shape is how leaks happen.
SENSITIVE_KEY_FRAGMENTS: tuple[str, ...] = (
    "api_key",
    "apikey",
    "app_password",
    "authorization",
    "credential",
    "password",
    "passwd",
    "secret",
    "access_token",
    "refresh_token",
    "auth_token",
    "api_token",
    # Storage paths are not credentials, but exposing one is a product bug
    # (ADR-007, roadmap 11.5).
    "storage_key",
)

# Matched whole, not as a fragment: `input_tokens` and `output_tokens` are the
# cost metadata art. VIII asks for, and redacting them would trade one
# constitutional duty for another.
SENSITIVE_EXACT_KEYS: frozenset[str] = frozenset({"token", "key", "auth", "authentication"})

# Free text is truncated: a log line is metadata, never a copy of the document.
MAX_VALUE_CHARS = 200
TRUNCATION_SUFFIX = "…[truncado]"


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    if lowered in SENSITIVE_EXACT_KEYS:
        return True
    return any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS)


def _scrub(value: Any) -> Any:  # noqa: ANN401 — a log value is genuinely arbitrary
    if isinstance(value, SecretStr):
        return REDACTED
    if isinstance(value, dict):
        return {
            key: REDACTED if _is_sensitive(str(key)) else _scrub(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return type(value)(_scrub(item) for item in value)
    if isinstance(value, str) and len(value) > MAX_VALUE_CHARS:
        return value[:MAX_VALUE_CHARS] + TRUNCATION_SUFFIX
    return value


def redact_sensitive(_logger: WrappedLogger, _name: str, event_dict: EventDict) -> EventDict:
    """Drop credentials by key name and truncate free text (art. V, FR-045)."""
    return {
        key: REDACTED if _is_sensitive(str(key)) else _scrub(value)
        for key, value in event_dict.items()
    }


def configure_logging(*, level: int = logging.INFO, stream: TextIO | None = None) -> None:
    """Install the processor chain. Idempotent, safe to call at every startup."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_sensitive,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=stream or sys.stdout),
        cache_logger_on_first_use=False,
    )


def bind_request_id(request_id: str) -> None:
    structlog.contextvars.bind_contextvars(request_id=request_id)


def bind_parse_job_id(parse_job_id: UUID | str) -> None:
    structlog.contextvars.bind_contextvars(parse_job_id=str(parse_job_id))


def clear_log_context() -> None:
    structlog.contextvars.clear_contextvars()


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
