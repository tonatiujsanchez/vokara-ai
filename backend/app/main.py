"""The FastAPI application.

Runs on the user's machine, listening on loopback, with no authentication
(ADR-008). Everything under /api/v1, which is what contracts/openapi.yaml
declares as its server and what the generated TypeScript client consumes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response

from app.api.errors import register_error_handlers
from app.api.v1 import health
from app.core.logging import bind_request_id, clear_log_context, configure_logging

API_V1_PREFIX = "/api/v1"
REQUEST_ID_HEADER = "X-Request-ID"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Vokara API",
        version="0.1.0",
        description=(
            "API local de Vokara. Sin autenticación (ADR-008): la instancia sirve a una "
            "sola persona, la que la instaló, y escucha únicamente en la interfaz local."
        ),
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def request_id_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """One identifier per request, on every log line it produces."""
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid4().hex
        bind_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            clear_log_context()
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    register_error_handlers(app)
    app.include_router(health.router, prefix=API_V1_PREFIX)

    return app


app = create_app()
