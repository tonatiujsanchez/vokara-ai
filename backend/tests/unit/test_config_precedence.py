"""Configuration precedence and credential redaction (research R-21, FR-008)."""

from __future__ import annotations

import ipaddress
import os
from pathlib import Path

import pytest
from pydantic import SecretStr

from app.core.config import Settings


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Precedence is only observable from a known starting point.

    Whoever runs the suite may have keys exported in their shell, and CI has
    them for the evals.
    """

    for name in list(os.environ):
        if name.startswith(("VOKARA_", "GOOGLE_", "GMAIL_")) or name in {
            "DATABASE_URL",
            "REDIS_URL",
        }:
            monkeypatch.delenv(name, raising=False)


def settings_from(env_file: Path) -> Settings:
    """Build Settings against a specific .env file.

    BaseSettings.__init__ accepts _env_file at runtime, but the typed signature
    mypy sees is synthesised from the model fields, so the keyword is invisible
    to it.
    """
    return Settings(_env_file=env_file)  # type: ignore[call-arg]


@pytest.fixture
def env_file(tmp_path: Path) -> Path:
    path = tmp_path / ".env"
    path.write_text(
        "\n".join(
            [
                "VOKARA_API_PORT=9001",
                "GOOGLE_API_KEY=from-file",
                "VOKARA_MIN_DOC_CHARS=111",
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_defaults_apply_when_nothing_is_configured(tmp_path: Path) -> None:
    settings = settings_from(tmp_path / "missing.env")

    assert settings.api_port == 8000
    assert settings.min_doc_chars == 200
    assert settings.google_api_key is None


def test_file_overrides_defaults(env_file: Path) -> None:
    settings = settings_from(env_file)

    assert settings.api_port == 9001
    assert settings.min_doc_chars == 111
    assert settings.google_api_key is not None
    assert settings.google_api_key.get_secret_value() == "from-file"


def test_environment_overrides_file(env_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOKARA_API_PORT", "9002")
    monkeypatch.setenv("GOOGLE_API_KEY", "from-environment")

    settings = settings_from(env_file)

    assert settings.api_port == 9002
    assert settings.google_api_key is not None
    assert settings.google_api_key.get_secret_value() == "from-environment"
    # Untouched keys still come from the file.
    assert settings.min_doc_chars == 111


def test_api_host_defaults_to_loopback(tmp_path: Path) -> None:
    """The default bind is the only access control there is (ADR-008)."""
    settings = settings_from(tmp_path / "missing.env")

    assert ipaddress.ip_address(settings.api_host).is_loopback


def test_credentials_are_secret_and_redacted_in_repr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Logging the settings object by accident must not leak a key (art. V)."""
    secret = "AIza-super-secret-value"
    monkeypatch.setenv("GOOGLE_API_KEY", secret)
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "abcd efgh ijkl mnop")

    settings = settings_from(tmp_path / "missing.env")

    assert isinstance(settings.google_api_key, SecretStr)
    assert isinstance(settings.gmail_app_password, SecretStr)

    for surface in (repr(settings), str(settings), str(settings.model_dump())):
        assert secret not in surface
        assert "super-secret" not in surface
        assert "abcd efgh" not in surface
