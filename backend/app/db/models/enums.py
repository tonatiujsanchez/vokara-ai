"""Native Postgres enum types, as seen from the ORM.

The values are also written in migration 0001, which is frozen on purpose: a
migration must not change what it created because a constant moved. T072 adds
domain/enums.py as StrEnum plus a parity test against the live database, which
is what keeps the copies honest.
"""

from __future__ import annotations

from sqlalchemy.dialects import postgresql

ENUM_VALUES: dict[str, tuple[str, ...]] = {
    "capability": ("generation", "embeddings"),
    "preflight_result": (
        "verified",
        "credential_rejected",
        "capability_unverified",
        "quota_exceeded",
    ),
    "email_step_status": ("pending", "linked", "skipped"),
    "profile_state": ("draft", "complete"),
    "entry_type": (
        "experience",
        "achievement",
        "education",
        "skill",
        "certification",
        "language",
        "project",
    ),
    "entry_origin": ("cv_seed", "user_added", "user_edited"),
    "version_origin": ("confirmation",),
    "parse_job_status": ("queued", "running", "succeeded", "failed"),
    "parse_job_step": ("extracting_text", "classifying", "extracting_entries", "persisting"),
    "document_kind": ("pdf", "docx"),
    "document_availability": ("available",),
    "remote_preference": ("onsite", "hybrid", "remote", "any"),
}


def pg_enum(name: str) -> postgresql.ENUM:
    """Reference the type the migration created; never create it as a side effect."""
    return postgresql.ENUM(*ENUM_VALUES[name], name=name, create_type=False)
