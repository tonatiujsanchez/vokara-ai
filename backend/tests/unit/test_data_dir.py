"""The data directory is resolved, created and proven writable (ADR-007)."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from app.core.data_dir import (
    DATA_DIR_UNUSABLE_MESSAGE,
    DataDirectoryError,
    ensure_data_dir,
    resolve_data_dir,
)


def test_relative_paths_become_absolute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    resolved = resolve_data_dir(Path("./data"))

    assert resolved.is_absolute()
    assert resolved == tmp_path.resolve() / "data"


def test_home_is_expanded(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    assert resolve_data_dir(Path("~/vokara")) == tmp_path.resolve() / "vokara"


def test_missing_directory_is_created(tmp_path: Path) -> None:
    """A fresh clone has no data directory: creating it is part of the install."""
    target = tmp_path / "nested" / "data"

    assert ensure_data_dir(target) == target.resolve()
    assert target.is_dir()


def test_existing_directory_is_reused(tmp_path: Path) -> None:
    target = tmp_path / "data"
    target.mkdir()
    (target / "keep.txt").write_text("ya estaba aqui", encoding="utf-8")

    ensure_data_dir(target)

    assert (target / "keep.txt").read_text(encoding="utf-8") == "ya estaba aqui"


def test_write_check_leaves_nothing_behind(tmp_path: Path) -> None:
    target = ensure_data_dir(tmp_path / "data")

    assert list(target.iterdir()) == []


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores permission bits")
def test_unwritable_directory_raises_an_actionable_error(tmp_path: Path) -> None:
    target = tmp_path / "data"
    target.mkdir()
    target.chmod(stat.S_IRUSR | stat.S_IXUSR)

    try:
        with pytest.raises(DataDirectoryError) as caught:
            ensure_data_dir(target)
    finally:
        target.chmod(stat.S_IRWXU)

    message = str(caught.value)
    assert message == DATA_DIR_UNUSABLE_MESSAGE
    # What to do next, and never the path (roadmap 11.5, art. V).
    assert "permisos" in message
    assert str(target) not in message


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores permission bits")
def test_uncreatable_directory_raises_the_same_error(tmp_path: Path) -> None:
    parent = tmp_path / "readonly"
    parent.mkdir()
    parent.chmod(stat.S_IRUSR | stat.S_IXUSR)

    try:
        with pytest.raises(DataDirectoryError) as caught:
            ensure_data_dir(parent / "data")
    finally:
        parent.chmod(stat.S_IRWXU)

    assert str(caught.value) == DATA_DIR_UNUSABLE_MESSAGE
    assert str(parent) not in str(caught.value)
