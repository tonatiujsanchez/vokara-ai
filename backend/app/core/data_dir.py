"""Resolution and verification of the local data directory (ADR-007).

This is where the original CVs live, unencrypted, on the user's own disk. When
it cannot be used, the message says what happened, why and what to do next, and
it never prints the path: a `PermissionError: /data` on screen is a product bug
(roadmap 11.5, errors.md "Errores de arranque y de entorno").
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

DATA_DIR_UNUSABLE_MESSAGE = (
    "Vokara no puede escribir en su directorio de datos. "
    "Revisa los permisos de esa carpeta o configura otra ruta con VOKARA_DATA_DIR."
)


class DataDirectoryError(RuntimeError):
    """The data directory cannot be used. Carries no path (art. V, roadmap 11.5)."""

    def __init__(self) -> None:
        super().__init__(DATA_DIR_UNUSABLE_MESSAGE)


def resolve_data_dir(configured: Path) -> Path:
    """Expand `~` and make the configured path absolute, without touching disk."""
    return Path(os.path.expandvars(str(configured))).expanduser().resolve()


def ensure_data_dir(configured: Path) -> Path:
    """Return the usable data directory, creating it when it does not exist.

    Creation is part of the contract: asking someone to `mkdir` before the first
    run is exactly the installation friction art. VII counts as scope.
    """
    path = resolve_data_dir(configured)

    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise DataDirectoryError from error

    if not path.is_dir():
        raise DataDirectoryError

    _assert_writable(path)
    return path


def _assert_writable(path: Path) -> None:
    """Prove writability by writing, not by asking os.access.

    os.access answers about permission bits; a read-only mount, a full disk or
    an ACL answers differently, and the user finds out mid-upload.
    """
    try:
        with tempfile.NamedTemporaryFile(dir=path, prefix=".vokara-write-check-"):
            pass
    except OSError as error:
        raise DataDirectoryError from error
