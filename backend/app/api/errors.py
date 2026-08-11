"""Domain error to HTTP response: {code, message, details}.

The shape is fixed by contracts/errors.md and it is the only shape errors take.
A stack trace on screen is a product bug, so the fallback handler answers the
catalogue's INTERNAL_ERROR and leaves the detail in the local log, where it
belongs (art. V, roadmap 11.5).
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.domain.errors import DomainError

logger = get_logger(__name__)


class ErrorResponse(BaseModel):
    """The only error body the API returns."""

    code: str = Field(description="Identificador estable en inglés del error.")
    message: str = Field(description="Texto accionable en español, resuelto por el backend.")
    details: dict[str, Any] | None = Field(
        default=None,
        description="Datos estructurados del error: campos inválidos, bloqueadores, límites.",
    )


def error_response(error: DomainError) -> JSONResponse:
    body = ErrorResponse(code=error.code, message=error.message, details=error.details)
    return JSONResponse(status_code=error.http_status, content=body.model_dump())


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
        body = ErrorResponse(
            code="VALIDATION_ERROR",
            message="Revisa los datos: hay campos con errores.",
            details={"fields": fields},
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=body.model_dump(),
        )

    @app.exception_handler(Exception)
    async def _unexpected_error(_request: Request, error: Exception) -> JSONResponse:
        # The detail stays in the local log; the response says what to do next.
        logger.error("unhandled_error", error_type=type(error).__name__)
        return error_response(DomainError())
