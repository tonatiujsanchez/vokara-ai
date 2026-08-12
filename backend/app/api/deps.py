"""Request dependencies.

`candidate_id` is resolved here, from local configuration, and no endpoint
accepts it as a parameter — not in the path, not in the query, not in the body,
not in a header (FR-003, FR-049). The day authentication exists, this function
is what changes; nothing downstream does (ADR-008).

There is no database session dependency on purpose: `api` never imports `db`
(art. II). Endpoints call services, and a service owns its own transaction.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends

from app.core.config import Settings, get_settings


def local_candidate_id(settings: Annotated[Settings, Depends(get_settings)]) -> UUID:
    return settings.candidate_id


CandidateId = Annotated[UUID, Depends(local_candidate_id)]
