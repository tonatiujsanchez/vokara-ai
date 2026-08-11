"""candidate onboarding

Revision ID: 0001
Revises:
Create Date: 2026-08-11

Nine tables, twelve enum types and the pgvector extension. Nothing speculative:
the design discarded an `onboarding_steps` table (the step is derived), a
`profile_entry_embeddings` table (no consumer in 001), a persisted
`has_unconfirmed_changes` flag (derived from the hash) and a credentials table
(they live in local configuration, never in the database — art. V, FR-008).

Part 1 (T021) creates the extension, the types and the tables in dependency
order. Part 2 (T022) adds the CHECKs, the indexes, the circular foreign key,
the immutability trigger and the seed row.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: None = None
depends_on: None = None

# Declared as native Postgres types so the database rejects out-of-domain
# values, and mirrored in domain/enums.py as StrEnum (data-model.md).
ENUM_TYPES: dict[str, tuple[str, ...]] = {
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
    # Feature 007 will add `cv_merge`. It is born with a single value on
    # purpose: no path in 001 can produce another origin (FR-040).
    "version_origin": ("confirmation",),
    "parse_job_status": ("queued", "running", "succeeded", "failed"),
    "parse_job_step": ("extracting_text", "classifying", "extracting_entries", "persisting"),
    "document_kind": ("pdf", "docx"),
    # Feature 006 will add deleted_by_candidate and purged_by_retention.
    "document_availability": ("available",),
    "remote_preference": ("onsite", "hybrid", "remote", "any"),
}


def enum(name: str) -> postgresql.ENUM:
    """Reference an already created type; never create it as a column side effect."""
    return postgresql.ENUM(*ENUM_TYPES[name], name=name, create_type=False)


def upgrade() -> None:
    bind = op.get_bind()

    # Enabled here so the feature that stores the first vector does not have to
    # touch infrastructure (research R-12). No vector is persisted in 001.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    for name, values in ENUM_TYPES.items():
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=False)

    # ── candidates ────────────────────────────────────────────────────────
    # Not an account: no email, no password, no session (ADR-008). It exists so
    # candidate_id is a real column from the first migration and every query is
    # born scoped by owner.
    op.create_table(
        "candidates",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_candidates"),
    )

    # ── setup_state ───────────────────────────────────────────────────────
    op.create_table(
        "setup_state",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("candidate_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("disclosure_acknowledged_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("disclosure_version", sa.Text(), nullable=True),
        sa.Column(
            "email_step_status",
            enum("email_step_status"),
            server_default=sa.text("'pending'::email_step_status"),
            nullable=False,
        ),
        # The designated label to read. Never the App Password (FR-013).
        sa.Column("email_label", sa.Text(), nullable=True),
        sa.Column("email_linked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_setup_state"),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name="fk_setup_state_candidate_id_candidates",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("candidate_id", name="uq_setup_state_candidate_id"),
    )

    # ── provider_configurations ───────────────────────────────────────────
    # One row per capability. Rows rather than columns is what makes generation
    # and embeddings genuinely independent (ADR-011, FR-004).
    op.create_table(
        "provider_configurations",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("candidate_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("capability", enum("capability"), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("preflight_result", enum("preflight_result"), nullable=False),
        sa.Column("preflight_at", sa.TIMESTAMP(timezone=True), nullable=False),
        # HMAC-SHA256 truncated, with a locally derived key. Not the credential
        # and not a fragment of it (research R-24, FR-008).
        sa.Column("credential_fingerprint", sa.Text(), nullable=False),
        sa.Column("embedding_dim", sa.Integer(), nullable=True),
        sa.Column("degradation_acknowledged_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_provider_configurations"),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name="fk_provider_configurations_candidate_id_candidates",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "candidate_id",
            "capability",
            name="uq_provider_configurations_candidate_id_capability",
        ),
    )

    # ── candidate_profiles ────────────────────────────────────────────────
    op.create_table(
        "candidate_profiles",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("candidate_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "state",
            enum("profile_state"),
            server_default=sa.text("'draft'::profile_state"),
            nullable=False,
        ),
        # Foreign key added in T022: it is circular with profile_versions.
        sa.Column("current_version_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("last_confirmed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("target_role", sa.Text(), nullable=True),
        sa.Column("salary_min", sa.Numeric(12, 2), nullable=True),
        sa.Column("salary_max", sa.Numeric(12, 2), nullable=True),
        sa.Column("salary_currency", sa.CHAR(3), nullable=True),
        sa.Column("remote_preference", enum("remote_preference"), nullable=True),
        sa.Column(
            "locations",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "industries",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "deal_breakers",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_candidate_profiles"),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name="fk_candidate_profiles_candidate_id_candidates",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("candidate_id", name="uq_candidate_profiles_candidate_id"),
    )

    # ── documents ─────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("candidate_id", sa.UUID(as_uuid=True), nullable=False),
        # Determined by byte signature, never by extension (research R-01).
        sa.Column("kind", enum("document_kind"), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        # Never exposed in an API response or an error message (ADR-007).
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column(
            "availability",
            enum("document_availability"),
            server_default=sa.text("'available'::document_availability"),
            nullable=False,
        ),
        sa.Column("availability_changed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name="fk_documents_candidate_id_candidates",
            ondelete="CASCADE",
        ),
    )

    # ── parse_jobs ────────────────────────────────────────────────────────
    op.create_table(
        "parse_jobs",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        # Denormalised on purpose: it is what the uniqueness index stands on.
        sa.Column("candidate_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            enum("parse_job_status"),
            server_default=sa.text("'queued'::parse_job_status"),
            nullable=False,
        ),
        sa.Column("step", enum("parse_job_step"), nullable=True),
        sa.Column(
            "progress_percent",
            sa.SmallInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        # A stable code from the catalogue, never a message with document data
        # (FR-045). There is no free-text error column, on purpose.
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("entries_created", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("truncated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("retry_of_job_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_parse_jobs"),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name="fk_parse_jobs_candidate_id_candidates",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_parse_jobs_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["retry_of_job_id"],
            ["parse_jobs.id"],
            name="fk_parse_jobs_retry_of_job_id_parse_jobs",
        ),
    )

    # ── profile_entries ───────────────────────────────────────────────────
    op.create_table(
        "profile_entries",
        # Stable for life (FR-025): this is the future source_id of art. IV.
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("profile_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_type", enum("entry_type"), nullable=False),
        sa.Column("origin", enum("entry_origin"), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("content_language", sa.CHAR(2), nullable=True),
        # Computed by rules, never by the model (FR-028).
        sa.Column("is_complete", sa.Boolean(), nullable=False),
        sa.Column(
            "missing_fields",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("source_document_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("source_excerpt", sa.Text(), nullable=True),
        # Logical delete: keeps the diff against the current version correct and
        # lets 007 avoid resurrecting what the candidate deleted (FR-032).
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_profile_entries"),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["candidate_profiles.id"],
            name="fk_profile_entries_profile_id_candidate_profiles",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"],
            ["documents.id"],
            name="fk_profile_entries_source_document_id_documents",
            ondelete="SET NULL",
        ),
    )

    # ── profile_versions ──────────────────────────────────────────────────
    op.create_table(
        "profile_versions",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("profile_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("origin", enum("version_origin"), nullable=False),
        # The whole entries, not references: a version must be readable even if
        # an entry is deleted afterwards (FR-041).
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_profile_versions"),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["candidate_profiles.id"],
            name="fk_profile_versions_profile_id_candidate_profiles",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "profile_id",
            "version_number",
            name="uq_profile_versions_profile_id_version_number",
        ),
    )

    # ── llm_call_logs ─────────────────────────────────────────────────────
    # No PII and no credentials by design: no prompts, no responses, no
    # candidate identifier, no free-text provider name (art. VIII, FR-046).
    op.create_table(
        "llm_call_logs",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("parse_job_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("capability", enum("capability"), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Numeric(10, 6), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("attempt", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_llm_call_logs"),
        sa.ForeignKeyConstraint(
            ["parse_job_id"],
            ["parse_jobs.id"],
            name="fk_llm_call_logs_parse_job_id_parse_jobs",
            ondelete="SET NULL",
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()

    for table in (
        "llm_call_logs",
        "profile_versions",
        "profile_entries",
        "parse_jobs",
        "documents",
        "candidate_profiles",
        "provider_configurations",
        "setup_state",
        "candidates",
    ):
        op.drop_table(table)

    for name, values in reversed(list(ENUM_TYPES.items())):
        postgresql.ENUM(*values, name=name).drop(bind, checkfirst=False)

    # Nothing else uses it in 001.
    op.execute("DROP EXTENSION IF EXISTS vector")
