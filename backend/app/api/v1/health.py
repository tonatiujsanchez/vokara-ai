"""GET /health — the endpoint that travels from Postgres to the browser."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.errors import error_responses
from app.services.health_service import read_health

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str = Field(description="`ok` cuando la instancia puede operar.")
    database: str = Field(description="`ok` cuando la base de datos responde.")
    migration_revision: str | None = Field(
        default=None,
        description="Revisión de Alembic aplicada, leída de la propia base.",
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Estado de la instancia local",
    responses=error_responses(),
)
def get_health() -> HealthResponse:
    report = read_health()
    return HealthResponse(
        status=report.status,
        database=report.database,
        migration_revision=report.migration_revision,
    )
