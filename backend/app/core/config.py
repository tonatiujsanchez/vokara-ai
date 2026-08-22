"""Typed configuration.

Precedence is environment > .env file > defaults, and the .env file lives in the
repository root and nowhere else (quickstart 0). Every credential is a
SecretStr: its repr is masked, so logging the settings object by accident does
not leak a key (art. V, FR-008, research R-21).

Nothing here is required to boot. Defaults are chosen so a fresh clone runs.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from uuid import UUID

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Seeded by migration 0001 as the single row of `candidates`. There are no
# accounts (ADR-008); this is the owner of the installation, resolved from
# configuration by the API layer and never accepted from the client (FR-003).
LOCAL_CANDIDATE_ID = UUID("0192f3a0-0001-7000-8000-000000000001")


def _find_repo_env_file() -> Path | None:
    """Walk up from this module looking for the single .env of the repository.

    Returns None inside the container, where Compose already injected the file
    contents as environment variables through `env_file: ../.env`.
    """
    for directory in Path(__file__).resolve().parents:
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_find_repo_env_file(),
        env_file_encoding="utf-8",
        env_prefix="VOKARA_",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Runtime ────────────────────────────────────────────────────────────
    # Loopback by default: with no authentication, where the instance listens
    # is the only access control there is (ADR-008). The container overrides it
    # to 0.0.0.0 because the Docker proxy cannot reach a loopback bind; there
    # the protection is the port mapping, not the bind.
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    database_url: str = Field(
        default="postgresql+psycopg://vokara:vokara_local_dev@127.0.0.1:5432/vokara",
        validation_alias=AliasChoices("VOKARA_DATABASE_URL", "DATABASE_URL"),
    )
    redis_url: str = Field(
        default="redis://127.0.0.1:6379/0",
        validation_alias=AliasChoices("VOKARA_REDIS_URL", "REDIS_URL"),
    )

    # Where the original CVs are stored, unencrypted (ADR-007).
    data_dir: Path = Path("./data")

    candidate_id: UUID = LOCAL_CANDIDATE_ID

    # ── Credentials ────────────────────────────────────────────────────────
    # Read from local configuration, never persisted in the database and never
    # present in logs, traces, error messages or API responses (FR-008, FR-013).
    #
    # ONE EXCEPTION TO THE PRECEDENCE ABOVE, AND IT ONLY APPLIES HERE.
    # For the credentials the first-run wizard captures — the API key of each
    # capability and the Gmail App Password — the file the wizard writes
    # (`<VOKARA_DATA_DIR>/credentials.env`) wins over the environment and over
    # `.env`. The fields below are the FALLBACK for those three, not the winner:
    # `adapters/llm/factory.py` and `services/email_link_service.py` resolve the
    # effective credential through `core/credentials.py`.
    #
    # Why the inversion: the wizard is the user's most recent and most explicit
    # action. If `.env` won, someone could paste a new key, see the preflight
    # turn green and have Vokara keep calling the provider with the old one,
    # silently — the kind of result-that-lies research R-24 exists to prevent,
    # and the opposite of the control art. X promises. When both are present the
    # UI says so instead of resolving it quietly (art. XI).
    #
    # Everything else on this class — model names, thresholds, data directory —
    # keeps environment > .env > defaults, so overriding by environment in a
    # container or in CI still works. Two precedences in one system is exactly
    # the thing that gets forgotten, which is why it is written down here and in
    # quickstart §0.
    google_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("VOKARA_GOOGLE_API_KEY", "GOOGLE_API_KEY"),
    )
    gmail_address: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VOKARA_GMAIL_ADDRESS", "GMAIL_ADDRESS"),
    )
    gmail_app_password: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("VOKARA_GMAIL_APP_PASSWORD", "GMAIL_APP_PASSWORD"),
    )
    gmail_label: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VOKARA_GMAIL_LABEL", "GMAIL_LABEL"),
    )

    # ── Model names ────────────────────────────────────────────────────────
    # In configuration, never as constants in code: a provider that retires a
    # model must not break an installation the user has not updated (ADR-011,
    # research R-21). Values verified on 2026-08-11 (ADR-011).
    google_model: str = "gemini-3.5-flash-lite"
    google_embed: str = "models/gemini-embedding-001"
    # MRL truncation from the 3072 the model returns by default (research R-12).
    embedding_dimensions: int = 768

    # ── Feature thresholds ─────────────────────────────────────────────────
    # Here rather than scattered as literals, so they can be calibrated against
    # the golden set without touching code (research R-03, R-14, R-21).
    max_upload_bytes: int = 10 * 1024 * 1024
    min_doc_chars: int = 200
    min_page_chars: int = 50
    classifier_chars: int = 6_000
    max_extraction_chars: int = 120_000
    min_seeded_entries: int = 3
    parse_job_poll_seconds: int = 2


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings, read once."""
    return Settings()
