"""Repository base with candidate_id in every signature.

There is one possible value today (ADR-008): no accounts, one installation, one
owner. Carrying it explicitly anyway costs one parameter now and saves
rewriting the data layer the day authentication arrives — that day the change
is *where the value comes from*, not how every query is written (research R-11).

A resource belonging to another candidate is absent, not forbidden: `get`
returns None and the API answers 404, never 403. Answering 403 would confirm
the resource exists (FR-049).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import Base


class CandidateScopedRepository[ModelT: Base]:
    """Every read is scoped by owner. There is no unscoped read."""

    model: ClassVar[type[Any]]
    # Tables that hang off the profile rather than the candidate override this
    # with their own join; the signature stays the same either way.
    scope_column: ClassVar[str] = "candidate_id"

    def __init__(self, session: Session) -> None:
        self.session = session

    def _owned_by(self, candidate_id: UUID) -> dict[str, UUID]:
        return {self.scope_column: candidate_id}

    def get(self, candidate_id: UUID, entity_id: UUID) -> ModelT | None:
        statement = select(self.model).filter_by(**self._owned_by(candidate_id), id=entity_id)
        result: ModelT | None = self.session.execute(statement).scalar_one_or_none()
        return result

    def list(self, candidate_id: UUID) -> Sequence[ModelT]:
        statement = select(self.model).filter_by(**self._owned_by(candidate_id))
        return list(self.session.execute(statement).scalars().all())

    def count(self, candidate_id: UUID) -> int:
        statement = (
            select(func.count()).select_from(self.model).filter_by(**self._owned_by(candidate_id))
        )
        return int(self.session.execute(statement).scalar_one())

    def exists(self, candidate_id: UUID, entity_id: UUID) -> bool:
        return self.get(candidate_id, entity_id) is not None

    def add(self, candidate_id: UUID, entity: ModelT) -> ModelT:
        """Stamp the owner on the way in, so it cannot be forgotten."""
        setattr(entity, self.scope_column, candidate_id)
        self.session.add(entity)
        self.session.flush()
        return entity
