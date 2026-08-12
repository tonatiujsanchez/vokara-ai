"""Health of the local installation, read from the database itself.

The revision comes from alembic_version rather than from a constant in the
code: what matters is the schema the instance is actually running, which after
an update the user has not restarted may not be the one the code expects
(ADR-009).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.logging import get_logger
from app.db.session import session_scope

logger = get_logger(__name__)


@dataclass(frozen=True)
class HealthReport:
    status: str
    database: str
    migration_revision: str | None


def read_health() -> HealthReport:
    try:
        with session_scope() as session:
            revision = session.execute(
                text("select version_num from alembic_version")
            ).scalar_one_or_none()
    except SQLAlchemyError as error:
        # The reason stays in the local log; the response says what is wrong
        # without a connection string or a stack trace in it (art. V).
        logger.warning("health_database_unavailable", error_type=type(error).__name__)
        return HealthReport(status="degraded", database="unavailable", migration_revision=None)

    return HealthReport(status="ok", database="ok", migration_revision=revision)
