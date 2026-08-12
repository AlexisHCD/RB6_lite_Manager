"""Safe user-scoped WirePlumber 0.4 override persistence."""

from __future__ import annotations

import os
import re
import tempfile
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath

from openbuds.core.config import BACKUP_DIR, resolve_xdg_home
from openbuds.core.errors import ConfigError
from openbuds.domain.interfaces import IConfigRepository
from openbuds.domain.interfaces.config_repo import ConfigBackup

USER_CONFIG_DIR = resolve_xdg_home("XDG_CONFIG_HOME", Path.home() / ".config") / "wireplumber"
BACKUP_DIR_DEFAULT = BACKUP_DIR
_BACKUP_NAME = re.compile(r"(?P<original>.+)\.\d{8}-\d{6}\.bak$")


class WirePlumberConfigEditor(IConfigRepository):
    """Persist WirePlumber 0.4 Lua overrides under the user XDG directory."""

    def __init__(
        self,
        base_dir: Path = USER_CONFIG_DIR,
        backup_dir: Path = BACKUP_DIR_DEFAULT,
        auto_rollback: bool = True,
    ) -> None:
        self._base_dir = base_dir.expanduser().resolve()
        self._backup_dir = backup_dir.expanduser().resolve()
        self._auto_rollback = auto_rollback

    def read_override(self, relative_path: str) -> str:
        """Read an override, returning an empty string when it is absent."""
        path = self._resolve(relative_path)
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""
        except (OSError, UnicodeError) as exc:
            raise ConfigError(f"Could not read WirePlumber override at {path}: {exc}") from exc

    def write_override(self, relative_path: str, content: str) -> ConfigBackup:
        """Write an override atomically after backing up its previous content."""
        path = self._resolve(relative_path)
        timestamp = _utc_timestamp()
        created_at = datetime.now(UTC).isoformat()
        backup_path = ""

        if path.exists():
            backup = self._backup_path(relative_path, timestamp)
            try:
                _atomic_copy(path, backup)
            except OSError as exc:
                raise ConfigError(f"Could not create WirePlumber backup for {path}: {exc}") from exc
            backup_path = str(backup)

        try:
            _atomic_write_text(path, content)
        except OSError as exc:
            raise ConfigError(f"Could not write WirePlumber override at {path}: {exc}") from exc

        try:
            self._verify_written_content(relative_path, content)
        except ConfigError as exc:
            if backup_path and self._auto_rollback:
                backup_reference = ConfigBackup(backup_path, str(path), created_at)
                try:
                    self.restore_from_backup(backup_reference)
                except ConfigError as rollback_exc:
                    raise ConfigError(
                        f"WirePlumber override verification failed at {path}; "
                        f"automatic rollback failed: {rollback_exc}"
                    ) from rollback_exc
                raise ConfigError(
                    f"WirePlumber override verification failed at {path}; "
                    "automatic rollback applied"
                ) from exc

            detail = (
                "no previous backup was available"
                if not backup_path
                else "automatic rollback is disabled"
            )
            raise ConfigError(
                f"WirePlumber override verification failed at {path}; {detail}"
            ) from exc

        return ConfigBackup(backup_path, str(path), created_at)

    def restore_from_backup(self, backup: ConfigBackup) -> None:
        """Restore a previous override and verify the restored bytes."""
        if not backup.backup_path:
            raise ConfigError("Cannot restore WirePlumber override: no backup is available")
        if not backup.original_path:
            raise ConfigError("Cannot restore WirePlumber override: original path is empty")

        original_path = self._validate_original_path(Path(backup.original_path))
        backup_path = Path(backup.backup_path)
        try:
            content = backup_path.read_bytes()
            _atomic_write_bytes(original_path, content)
            restored = original_path.read_bytes()
        except OSError as exc:
            raise ConfigError(
                f"Could not restore WirePlumber override from {backup_path}: {exc}"
            ) from exc

        if restored != content:
            raise ConfigError(f"WirePlumber rollback verification failed for {original_path}")

    def list_backups(self) -> list[ConfigBackup]:
        """List available backups from newest to oldest."""
        if not self._backup_dir.is_dir():
            return []

        backups: list[tuple[float, ConfigBackup]] = []
        try:
            paths = self._backup_dir.glob("*.bak")
            for path in paths:
                stat = path.stat()
                original_name = _original_name(path.name)
                created_at = datetime.fromtimestamp(stat.st_mtime, UTC).isoformat()
                backups.append(
                    (
                        stat.st_mtime,
                        ConfigBackup(
                            str(path),
                            str(self._base_dir / original_name),
                            created_at,
                        ),
                    )
                )
        except OSError as exc:
            raise ConfigError(f"Could not list WirePlumber backups: {exc}") from exc

        backups.sort(key=lambda item: item[0], reverse=True)
        return [backup for _, backup in backups]

    def _resolve(self, relative_path: str) -> Path:
        """Resolve a relative override path while rejecting traversal."""
        if not isinstance(relative_path, str) or not relative_path or "\x00" in relative_path:
            raise ValueError("relative_path must be a non-empty path without NUL bytes")

        normalized = relative_path.replace("\\", "/")
        candidate = Path(normalized)
        windows_candidate = PureWindowsPath(relative_path)
        if (
            candidate.is_absolute()
            or windows_candidate.is_absolute()
            or bool(windows_candidate.drive)
            or ".." in candidate.parts
        ):
            raise ValueError(f"Unsafe WirePlumber override path: {relative_path!r}")

        resolved = (self._base_dir / candidate).resolve()
        if not resolved.is_relative_to(self._base_dir):
            raise ValueError(f"Unsafe WirePlumber override path: {relative_path!r}")
        return self._base_dir / candidate

    def _backup_path(self, relative_path: str, timestamp: str) -> Path:
        """Build the flat, timestamped name used for a WirePlumber backup."""
        sanitized = relative_path.replace("/", "_").replace("\\", "_")
        return self._backup_dir / f"{sanitized}.{timestamp}.bak"

    def _verify_written_content(self, relative_path: str, expected: str) -> None:
        """Verify the text installed at a relative override path."""
        try:
            actual = self.read_override(relative_path)
        except ConfigError as exc:
            raise ConfigError(
                f"Could not verify WirePlumber override at {relative_path}: {exc}"
            ) from exc
        if actual != expected:
            raise ConfigError(f"WirePlumber override verification differed at {relative_path}")

    def _validate_original_path(self, path: Path) -> Path:
        """Ensure a restore target remains inside the configured user scope."""
        resolved = path.expanduser().resolve()
        if not resolved.is_relative_to(self._base_dir):
            raise ConfigError(f"Unsafe WirePlumber restore target: {path}")
        return resolved


def _atomic_copy(source: Path, destination: Path) -> None:
    """Copy bytes through an fsynced temporary file in the destination directory."""
    _atomic_write_bytes(destination, source.read_bytes())


def _atomic_write_text(path: Path, content: str) -> None:
    """Write UTF-8 text atomically."""
    _atomic_write_bytes(path, content.encode("utf-8"))


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    """Write bytes through a same-directory fsynced temporary file."""
    temporary_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            with suppress(OSError):
                temporary_path.unlink()


def _original_name(backup_name: str) -> str:
    """Estimate the original basename encoded by a flattened backup name."""
    match = _BACKUP_NAME.fullmatch(backup_name)
    if match is not None:
        return match.group("original")
    return backup_name.removesuffix(".bak")


def _utc_timestamp() -> str:
    """Return the filename timestamp used by versioned backups."""
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
