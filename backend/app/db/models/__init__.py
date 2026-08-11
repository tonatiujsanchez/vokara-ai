"""Typed SQLAlchemy 2.0 models (Mapped[...]).

Imported for their side effect of registering on Base.metadata, which is what
Alembic compares against.
"""

from app.db.models.candidate import Candidate
from app.db.models.provider_configuration import ProviderConfiguration
from app.db.models.setup_state import SetupState

__all__ = [
    "Candidate",
    "ProviderConfiguration",
    "SetupState",
]
