"""Typed SQLAlchemy 2.0 models (Mapped[...]).

Imported for their side effect of registering on Base.metadata, which is what
Alembic compares against.
"""

from app.db.models.candidate import Candidate
from app.db.models.candidate_profile import CandidateProfile
from app.db.models.document import Document
from app.db.models.llm_call_log import LlmCallLog
from app.db.models.parse_job import ParseJob
from app.db.models.profile_entry import ProfileEntry
from app.db.models.profile_version import ProfileVersion
from app.db.models.provider_configuration import ProviderConfiguration
from app.db.models.setup_state import SetupState

__all__ = [
    "Candidate",
    "CandidateProfile",
    "Document",
    "LlmCallLog",
    "ParseJob",
    "ProfileEntry",
    "ProfileVersion",
    "ProviderConfiguration",
    "SetupState",
]
