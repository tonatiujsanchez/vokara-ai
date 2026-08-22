"""Credentials the wizard writes, in a local file the wizard owns (FR-008, FR-013).

The candidate pastes their API key on screen, not into a file: that is the whole
point of the wizard, and quickstart §0 states it as a requirement — «si algún
paso requiere editar un archivo a mano más allá de lo que el wizard pide, eso es
un hallazgo». So the key has to be written somewhere, and this module is the
only place that decides where.

**Where.** `<VOKARA_DATA_DIR>/credentials.env`, mode 0600. Not the repository's
`.env`, for a mechanical reason: the documented run mounts nothing of the repo
into the containers — Compose reads `../.env` and injects its contents as
environment variables — so the file simply is not reachable from inside the
process that would have to write it. The data directory is, it already persists
in a volume, and it is where ADR-007 puts everything else that is the user's.

**Precedence: this file wins over the environment and over `.env`, and only for
these credentials.** It is the reverse of the rule that governs the rest of the
configuration (research R-21), and the exception is deliberate: the wizard is
the user's most recent, most explicit action. If `.env` won, someone could paste
a new key, watch the preflight turn green and have the application keep calling
the provider with the old one, with no visible error anywhere — a result that
lies, of the same family research R-24 exists to prevent, and the opposite of
what art. X asks of a system that says «Vokara propone; el candidato decide».

The exception stops at credentials the wizard manages. Model names, thresholds
and `VOKARA_DATA_DIR` keep environment > `.env` > defaults, so overriding them
in CI or in a container still works (see the note in `core/config.py`).

**What is never here.** The file holds credentials, so it is never logged, never
returned by an endpoint and never persisted in the database. What reaches the
database is the fingerprint of research R-24, which is a digest and not a
fragment of the key.
"""

from __future__ import annotations

import contextlib
import os
import secrets
from enum import StrEnum
from pathlib import Path

from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.core.data_dir import ensure_data_dir, resolve_data_dir
from app.domain.capability import Capability

CREDENTIALS_FILENAME = "credentials.env"
INSTALLATION_KEY_FILENAME = ".installation-key"

# Owner read/write only. The file sits next to the CVs, which ADR-007 already
# leaves unencrypted, so this is not the protection — disk encryption is — but
# there is no reason to hand it to every account on the machine either.
_PRIVATE_FILE_MODE = 0o600

_FILE_HEADER = """\
# Credenciales escritas por el asistente de primera ejecución de Vokara.
#
# Este archivo tiene prioridad sobre .env y sobre las variables de entorno para
# estas credenciales: lo que configuraste en pantalla es lo que Vokara usa.
# Bórralo para volver a lo que diga tu .env.
#
# No lo compartas: contiene tus llaves en claro.
"""


class WizardCredential(StrEnum):
    """The credentials the first-run wizard captures, by the name it stores them under."""

    GENERATION_API_KEY = "VOKARA_GENERATION_API_KEY"
    EMBEDDINGS_API_KEY = "VOKARA_EMBEDDINGS_API_KEY"
    GMAIL_APP_PASSWORD = "VOKARA_GMAIL_APP_PASSWORD"  # noqa: S105 — a name, not a value


class WizardSetting(StrEnum):
    """Not secret, but captured by the wizard and stored in the same file.

    The mail address is the candidate's, so it is theirs and not a value to
    scatter: it lives beside the App Password it belongs to, out of the
    database, and it is the one piece of that step the adapter needs to connect.
    """

    GMAIL_ADDRESS = "VOKARA_GMAIL_ADDRESS"


def api_key_of(capability: Capability) -> WizardCredential:
    """The stored name of the API key of one capability.

    Keyed by capability and not by provider, which is what makes rotating one
    key invalidate one preflight: generation and embeddings are configured
    separately even when the same provider serves both (FR-004, research R-24).
    """
    match capability:
        case Capability.GENERATION:
            return WizardCredential.GENERATION_API_KEY
        case Capability.EMBEDDINGS:
            return WizardCredential.EMBEDDINGS_API_KEY


def credentials_path(settings: Settings | None = None) -> Path:
    return resolve_data_dir((settings or get_settings()).data_dir) / CREDENTIALS_FILENAME


def _parse(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, _, value = stripped.partition("=")
        values[name.strip()] = value.strip()
    return values


def _read_all(settings: Settings | None = None) -> dict[str, str]:
    """Read from disk every time. A cache here would hide a rotation (R-24)."""
    path = credentials_path(settings)
    if not path.is_file():
        return {}
    return _parse(path.read_text(encoding="utf-8"))


def read_credential(name: WizardCredential, settings: Settings | None = None) -> SecretStr | None:
    """The credential the wizard stored, or `None` if it never stored one."""
    value = _read_all(settings).get(name.value)
    return SecretStr(value) if value else None


def read_setting(name: WizardSetting, settings: Settings | None = None) -> str | None:
    """A non-secret value the wizard stored, in plain text because it is not one."""
    return _read_all(settings).get(name.value) or None


def write_setting(name: WizardSetting, value: str, settings: Settings | None = None) -> None:
    """Store a non-secret value the wizard captured, in the same local file."""
    write_credential(name, SecretStr(value), settings)


def write_credential(
    name: WizardCredential | WizardSetting, credential: SecretStr, settings: Settings | None = None
) -> None:
    """Store a credential, replacing whatever was under that name.

    Written **before** the credential is verified, on purpose: it is what lets a
    preflight that could not reach the provider be retried without asking the
    candidate to paste the key again, which the edge case of the spec asks for
    explicitly.
    """
    resolved = (settings or get_settings()).data_dir
    directory = ensure_data_dir(resolved)
    path = directory / CREDENTIALS_FILENAME

    value = credential.get_secret_value()
    if "\n" in value or "\r" in value:
        raise ValueError("a credential cannot contain a line break")

    values = _parse(path.read_text(encoding="utf-8")) if path.is_file() else {}
    values[name.value] = value

    body = _FILE_HEADER + "\n" + "\n".join(f"{key}={item}" for key, item in values.items()) + "\n"
    _write_private(path, body)


def forget_credential(
    name: WizardCredential | WizardSetting, settings: Settings | None = None
) -> None:
    """Drop one stored credential, leaving the others in place."""
    path = credentials_path(settings)
    if not path.is_file():
        return

    values = _parse(path.read_text(encoding="utf-8"))
    if values.pop(name.value, None) is None:
        return

    body = _FILE_HEADER + "\n" + "\n".join(f"{key}={item}" for key, item in values.items()) + "\n"
    _write_private(path, body)


def installation_key(settings: Settings | None = None) -> bytes:
    """The local secret the credential fingerprint is keyed with (research R-24).

    Random, generated once per installation and never leaving it. It is what
    makes the stored fingerprint useless anywhere else: without it a digest of
    a short API key would be a digest anyone could recompute.
    """
    directory = ensure_data_dir((settings or get_settings()).data_dir)
    path = directory / INSTALLATION_KEY_FILENAME

    if path.is_file():
        stored = path.read_text(encoding="utf-8").strip()
        if stored:
            return bytes.fromhex(stored)

    generated = secrets.token_bytes(32)
    _write_private(path, generated.hex() + "\n")
    return generated


def _write_private(path: Path, body: str) -> None:
    """Create with 0600 from the start, so the content is never world-readable."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, _PRIVATE_FILE_MODE)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(body)

    # Windows and some mounted filesystems do not carry POSIX modes. The file is
    # still written; the mode is a best effort, not a guarantee we would be
    # honest claiming.
    with contextlib.suppress(OSError):
        path.chmod(_PRIVATE_FILE_MODE)
