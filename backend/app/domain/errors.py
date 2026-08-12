"""Domain error hierarchy.

Every error carries a stable English `code`, an actionable Spanish `message` and
optional structured `details`. The catalogue of codes and texts is
specs/001-candidate-onboarding/contracts/errors.md, and it is the single owner
of the wording: the frontend shows `message` as is and branches only on `code`
(art. IX, errors.md "Uso desde el frontend").

Three rules hold for every message here:

1. No document content and no personal data (FR-045). Messages are fixed
   templates; the only interpolated values are limits the system configures.
2. No credential, complete or partial, and no technical trace (FR-008, FR-013).
3. What happened, why, and the concrete next step. Without a next step the
   message is incomplete — in a local installation it is all the support there
   is (roadmap 11.5).
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base of every error the product can explain to the candidate."""

    code: str = "INTERNAL_ERROR"
    message: str = (
        "Ocurrió un error inesperado. Inténtalo de nuevo; si persiste, abre un issue "
        "con lo que aparece en la pantalla de diagnóstico."
    )
    http_status: int = 500

    def __init__(self, details: dict[str, Any] | None = None) -> None:
        super().__init__(self.message)
        self.details = details
