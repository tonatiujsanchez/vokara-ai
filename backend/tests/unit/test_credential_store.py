"""The wizard's credential file: where it lives, who wins, and what it never does.

The inverted precedence is the reason this file exists, so it is the first thing
tested: a candidate who pastes a key on screen and sees the preflight turn green
must not have Vokara keep calling the provider with the key from an old `.env`.
"""

from __future__ import annotations

import stat
import sys
from pathlib import Path

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.core.credentials import (
    CREDENTIALS_FILENAME,
    WizardCredential,
    api_key_of,
    credentials_path,
    forget_credential,
    installation_key,
    read_credential,
    write_credential,
)
from app.domain.capability import Capability

A_KEY = "AIza-una-llave-de-prueba-que-no-existe"
ANOTHER_KEY = "AIza-otra-llave-distinta"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path)


def test_a_credential_survives_the_round_trip(settings: Settings) -> None:
    write_credential(WizardCredential.GENERATION_API_KEY, SecretStr(A_KEY), settings)

    stored = read_credential(WizardCredential.GENERATION_API_KEY, settings)

    assert stored is not None
    assert stored.get_secret_value() == A_KEY


def test_nothing_stored_reads_as_nothing(settings: Settings) -> None:
    assert read_credential(WizardCredential.EMBEDDINGS_API_KEY, settings) is None


def test_it_lives_in_the_data_directory_and_not_in_the_repository(settings: Settings) -> None:
    """The container mounts no repository file it could write to instead."""
    write_credential(WizardCredential.GENERATION_API_KEY, SecretStr(A_KEY), settings)

    path = credentials_path(settings)

    assert path.name == CREDENTIALS_FILENAME
    assert path.parent == settings.data_dir.resolve()
    assert path.is_file()


def test_each_capability_has_its_own_credential(settings: Settings) -> None:
    """Rotating one key must not touch the other capability (research R-24)."""
    write_credential(api_key_of(Capability.GENERATION), SecretStr(A_KEY), settings)
    write_credential(api_key_of(Capability.EMBEDDINGS), SecretStr(ANOTHER_KEY), settings)

    write_credential(api_key_of(Capability.GENERATION), SecretStr("una-tercera"), settings)

    generation = read_credential(api_key_of(Capability.GENERATION), settings)
    embeddings = read_credential(api_key_of(Capability.EMBEDDINGS), settings)
    assert generation is not None
    assert generation.get_secret_value() == "una-tercera"
    assert embeddings is not None
    assert embeddings.get_secret_value() == ANOTHER_KEY


def test_forgetting_one_leaves_the_others_alone(settings: Settings) -> None:
    write_credential(WizardCredential.GENERATION_API_KEY, SecretStr(A_KEY), settings)
    write_credential(WizardCredential.GMAIL_APP_PASSWORD, SecretStr(ANOTHER_KEY), settings)

    forget_credential(WizardCredential.GENERATION_API_KEY, settings)

    assert read_credential(WizardCredential.GENERATION_API_KEY, settings) is None
    assert read_credential(WizardCredential.GMAIL_APP_PASSWORD, settings) is not None


def test_every_read_goes_to_disk_so_a_rotation_is_noticed(settings: Settings) -> None:
    """A cache here would make the fingerprint comparison of R-24 pointless."""
    write_credential(WizardCredential.GENERATION_API_KEY, SecretStr(A_KEY), settings)
    read_credential(WizardCredential.GENERATION_API_KEY, settings)

    credentials_path(settings).write_text(
        f"{WizardCredential.GENERATION_API_KEY.value}={ANOTHER_KEY}\n", encoding="utf-8"
    )

    rotated = read_credential(WizardCredential.GENERATION_API_KEY, settings)
    assert rotated is not None
    assert rotated.get_secret_value() == ANOTHER_KEY


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes are not carried on Windows")
def test_the_file_is_readable_by_its_owner_only(settings: Settings) -> None:
    write_credential(WizardCredential.GENERATION_API_KEY, SecretStr(A_KEY), settings)

    mode = credentials_path(settings).stat().st_mode

    assert stat.S_IMODE(mode) == 0o600


def test_a_credential_with_a_line_break_is_refused(settings: Settings) -> None:
    """It would corrupt the file and split a key across two names."""
    with pytest.raises(ValueError, match="line break"):
        write_credential(WizardCredential.GENERATION_API_KEY, SecretStr("una\nllave"), settings)


def test_the_installation_key_is_generated_once_and_kept(settings: Settings) -> None:
    """Keyed with it, the fingerprint is useless outside this installation (R-24)."""
    first = installation_key(settings)
    again = installation_key(settings)

    assert first == again
    assert len(first) == 32


def test_two_installations_do_not_share_the_installation_key(tmp_path: Path) -> None:
    mine = installation_key(Settings(data_dir=tmp_path / "mia"))
    theirs = installation_key(Settings(data_dir=tmp_path / "ajena"))

    assert mine != theirs


def test_the_stored_credential_never_reaches_a_repr(settings: Settings) -> None:
    """`SecretStr` masks itself, which is the second net under the redactor."""
    write_credential(WizardCredential.GENERATION_API_KEY, SecretStr(A_KEY), settings)

    stored = read_credential(WizardCredential.GENERATION_API_KEY, settings)

    assert A_KEY not in repr(stored)
    assert A_KEY not in str(stored)
