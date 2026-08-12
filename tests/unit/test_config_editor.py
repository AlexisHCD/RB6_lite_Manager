"""Unit tests for safe WirePlumber override persistence."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from openbuds.core.errors import ConfigError
from openbuds.domain.interfaces.config_repo import ConfigBackup
from openbuds.infrastructure.wireplumber import config_editor
from openbuds.infrastructure.wireplumber.config_editor import WirePlumberConfigEditor


def _editor(tmp_path: Path) -> WirePlumberConfigEditor:
    return WirePlumberConfigEditor(tmp_path / "wireplumber", tmp_path / "backups")


def test_read_override_returns_content_or_empty(tmp_path: Path) -> None:
    editor = _editor(tmp_path)
    path = tmp_path / "wireplumber" / "bluetooth.lua.d" / "50-config.lua"
    path.parent.mkdir(parents=True)
    path.write_text("content", encoding="utf-8")

    assert editor.read_override("bluetooth.lua.d/50-config.lua") == "content"
    assert editor.read_override("missing.lua") == ""


def test_write_override_creates_backup_and_verifies_content(tmp_path: Path) -> None:
    editor = _editor(tmp_path)
    path = tmp_path / "wireplumber" / "bluetooth.lua.d" / "50-config.lua"
    path.parent.mkdir(parents=True)
    path.write_text("old", encoding="utf-8")

    backup = editor.write_override("bluetooth.lua.d/50-config.lua", "new")

    assert backup.backup_path
    assert Path(backup.backup_path).read_text(encoding="utf-8") == "old"
    assert editor.read_override("bluetooth.lua.d/50-config.lua") == "new"
    assert backup.original_path == str(path)
    assert backup.created_at.endswith("+00:00")


def test_write_override_without_previous_file_has_no_backup(tmp_path: Path) -> None:
    editor = _editor(tmp_path)

    backup = editor.write_override("new.lua", "content")

    assert backup.backup_path == ""
    assert editor.read_override("new.lua") == "content"


@pytest.mark.parametrize("relative_path", ["../x", "/abs", "a/../../b", "unsafe\x00.lua"])
def test_resolve_rejects_unsafe_paths(tmp_path: Path, relative_path: str) -> None:
    editor = _editor(tmp_path)

    with pytest.raises(ValueError):
        editor.read_override(relative_path)


def test_backup_failure_preserves_original(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    editor = _editor(tmp_path)
    path = tmp_path / "wireplumber" / "config.lua"
    path.parent.mkdir(parents=True)
    path.write_text("old", encoding="utf-8")

    def fail_copy(*args: object, **kwargs: object) -> None:
        raise OSError("backup denied")

    monkeypatch.setattr(config_editor, "_atomic_copy", fail_copy)

    with pytest.raises(ConfigError, match="backup"):
        editor.write_override("config.lua", "new")

    assert path.read_text(encoding="utf-8") == "old"


def test_verification_failure_rolls_back_previous_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    editor = _editor(tmp_path)
    path = tmp_path / "wireplumber" / "config.lua"
    path.parent.mkdir(parents=True)
    path.write_text("old", encoding="utf-8")

    def fail_verification(_relative_path: str, _expected: str) -> None:
        raise ConfigError("verification failed")

    monkeypatch.setattr(editor, "_verify_written_content", fail_verification)

    with pytest.raises(ConfigError, match="rollback applied"):
        editor.write_override("config.lua", "new")

    assert path.read_text(encoding="utf-8") == "old"


def test_restore_from_backup_requires_a_backup(tmp_path: Path) -> None:
    editor = _editor(tmp_path)
    reference = ConfigBackup("", str(tmp_path / "wireplumber" / "config.lua"), "now")

    with pytest.raises(ConfigError, match="no backup"):
        editor.restore_from_backup(reference)


def test_restore_from_backup_restores_previous_content(tmp_path: Path) -> None:
    editor = _editor(tmp_path)
    path = tmp_path / "wireplumber" / "config.lua"
    path.parent.mkdir(parents=True)
    path.write_text("old", encoding="utf-8")
    backup = editor.write_override("config.lua", "new")
    path.write_text("changed", encoding="utf-8")

    editor.restore_from_backup(backup)

    assert path.read_text(encoding="utf-8") == "old"


def test_list_backups_returns_newest_first(tmp_path: Path) -> None:
    editor = _editor(tmp_path)
    old_path = tmp_path / "wireplumber" / "old.lua"
    new_path = tmp_path / "wireplumber" / "new.lua"
    old_path.parent.mkdir(parents=True)
    old_path.write_text("old before", encoding="utf-8")
    new_path.write_text("new before", encoding="utf-8")

    old_backup = editor.write_override("old.lua", "old after")
    new_backup = editor.write_override("new.lua", "new after")
    os.utime(old_backup.backup_path, (100.0, 100.0))
    os.utime(new_backup.backup_path, (200.0, 200.0))

    backups = editor.list_backups()

    assert [backup.backup_path for backup in backups] == [
        new_backup.backup_path,
        old_backup.backup_path,
    ]
    assert backups[0].original_path == str(tmp_path / "wireplumber" / "new.lua")
