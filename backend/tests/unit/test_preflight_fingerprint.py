"""The fingerprint: enough to notice a rotation, useless as a copy of the key.

Research R-24 needs two properties at once and they pull in opposite directions:
the stored value must change when the credential changes, and it must not be the
credential «ni completa ni parcialmente» (FR-008). What squares them is an HMAC
keyed with a secret that never leaves the installation.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.services.preflight_service import FINGERPRINT_CHARS, fingerprint

A_KEY = "AIzaSyD-una-llave-de-prueba-que-no-existe"
ANOTHER_KEY = "AIzaSyD-una-llave-de-prueba-que-no-existf"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path)


def test_the_same_credential_fingerprints_the_same_way(settings: Settings) -> None:
    """Otherwise every read would look like a rotation."""
    assert fingerprint(SecretStr(A_KEY), settings) == fingerprint(SecretStr(A_KEY), settings)


def test_a_credential_that_changes_by_one_character_changes_the_digest(
    settings: Settings,
) -> None:
    """Pasting a nearly identical key is the realistic mistake to catch."""
    assert fingerprint(SecretStr(A_KEY), settings) != fingerprint(SecretStr(ANOTHER_KEY), settings)


def test_two_installations_fingerprint_the_same_key_differently(tmp_path: Path) -> None:
    """Keyed, so the digest says nothing to anyone who did not generate the key."""
    mine = fingerprint(SecretStr(A_KEY), Settings(data_dir=tmp_path / "mia"))
    theirs = fingerprint(SecretStr(A_KEY), Settings(data_dir=tmp_path / "ajena"))

    assert mine != theirs


def test_the_digest_contains_no_part_of_the_credential(settings: Settings) -> None:
    """«Ni siquiera parcialmente» is the wording of FR-008, so it is tested that way."""
    digest = fingerprint(SecretStr(A_KEY), settings)

    assert A_KEY not in digest
    for length in range(4, len(A_KEY)):
        assert A_KEY[:length] not in digest
        assert A_KEY[-length:] not in digest


def test_the_digest_is_a_fixed_length_hex_string(settings: Settings) -> None:
    """Fixed length: its size reveals nothing about the length of the key either."""
    short = fingerprint(SecretStr("x"), settings)
    long = fingerprint(SecretStr(A_KEY * 4), settings)

    assert len(short) == len(long) == FINGERPRINT_CHARS
    assert int(short, 16) >= 0
