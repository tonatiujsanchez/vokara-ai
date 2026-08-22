"""Domain error to HTTP response: {code, message, details}.

The shape is fixed by contracts/errors.md and it is the only shape errors take.
A stack trace on screen is a product bug, so the fallback handler answers the
catalogue's INTERNAL_ERROR and leaves the detail in the local log, where it
belongs (art. V, roadmap 11.5).

**The contract declares this shape, and so does this module.** `contracts/
openapi.yaml` already referenced `Error` on every error response of every
endpoint; what the generated schema published was FastAPI's own
`HTTPValidationError` on the 422s — a body this application never returns,
because the handler below intercepts `RequestValidationError` and answers the
catalogue instead. `error_responses()` closes that gap: the routes declare what
they actually return, the generated client types it, and CI's drift check sees
a rename (art. I).
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.domain.errors import DomainError, ErrorCode, ValidationFailedError

logger = get_logger(__name__)


class Error(BaseModel):
    """The only error body the API returns.

    Named after the schema of `contracts/openapi.yaml`, because the component
    key OpenAPI publishes is this class's name: calling it anything else would
    put a second name for the same thing in the generated client. It is the
    error *body*; the exception that produces it is `DomainError`.
    """

    code: ErrorCode = Field(
        description=(
            "Identificador estable en inglés del error. Conjunto cerrado: el frontend "
            "ramifica sobre él y no puede ramificar sobre uno inexistente."
        )
    )
    message: str = Field(description="Texto accionable en español, resuelto por el backend.")
    details: dict[str, Any] | None = Field(
        default=None,
        description="Datos estructurados del error: campos inválidos, bloqueadores, límites.",
    )


def error_response(error: DomainError) -> JSONResponse:
    body = Error(code=error.code, message=error.message, details=error.details)
    return JSONResponse(status_code=error.http_status, content=body.model_dump(mode="json"))


def error_responses(*errors: type[DomainError]) -> dict[int | str, dict[str, Any]]:
    """What an endpoint may answer with, grouped by status, for the OpenAPI.

    `DomainError` is appended to every group because the fallback handler can
    turn any unclassified exception into its INTERNAL_ERROR: an endpoint that
    did not declare a 500 would be describing a response it can still produce.

    Declaring a 422 here also **replaces** the `HTTPValidationError` FastAPI adds
    on its own to any route with a parameter or a body. That substitution is the
    point: this application never returns that body.
    """
    declared: tuple[type[DomainError], ...] = (*errors, DomainError)
    grouped: dict[int, set[ErrorCode]] = {}
    for error in declared:
        grouped.setdefault(error.http_status, set()).add(error.code)

    return {
        status: {
            "model": Error,
            "description": " · ".join(sorted(code.value for code in codes)),
        }
        for status, codes in sorted(grouped.items())
    }


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain_error(_request: Request, error: Exception) -> JSONResponse:
        # Starlette hands the handler an Exception; narrowing keeps the response
        # shape total instead of resting on the framework's promise.
        domain_error = error if isinstance(error, DomainError) else DomainError()
        logger.info("domain_error", code=domain_error.code, http_status=domain_error.http_status)
        return error_response(domain_error)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, error: Exception) -> JSONResponse:
        raw = error.errors() if isinstance(error, RequestValidationError) else []
        fields = {".".join(str(part) for part in item["loc"][1:]): item["msg"] for item in raw}
        return error_response(ValidationFailedError(fields=fields))

    @app.exception_handler(Exception)
    async def _unexpected_error(_request: Request, error: Exception) -> JSONResponse:
        # The detail stays in the local log; the response says what to do next.
        logger.error("unhandled_error", error_type=type(error).__name__)
        return error_response(DomainError())
