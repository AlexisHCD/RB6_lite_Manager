"""Configuración de la propia aplicación OpenBuds (no del sistema).

Distinguir de ``infrastructure.persistence`` (que persiste el estado de
runtime). Este módulo carga y guarda los ajustes estáticos del usuario desde
un archivo de configuración TOML en ``$XDG_CONFIG_HOME/openbuds/`` (o su
fallback ``~/.config/openbuds/``).

Formato del archivo (escritura manual para preservar comentarios; ver
``docs/ADR/0006-app-config-toml-xdg-atomic-write.md``):

    [openbuds]
    log_level = "INFO"
    log_file = ""
    backup_dir = "~/.local/share/openbuds/backups"
    auto_rollback_on_error = true
    experimental_features = false
"""

from __future__ import annotations

import json
import os
import tempfile
import tomllib
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from openbuds.core.errors import ConfigError


def resolve_xdg_home(variable: str, fallback: Path) -> Path:
    """Resuelve una base XDG válida sin leer configuración adicional.

    Solo se aceptan valores no vacíos y absolutos. Los valores inválidos se
    sustituyen por el fallback recibido, lo que permite probar la resolución
    sin modificar ``HOME`` ni depender del entorno real.
    """
    value = os.environ.get(variable)
    if value:
        candidate = Path(value)
        if candidate.is_absolute():
            return candidate
    return fallback


# Directorios base del usuario según la especificación XDG.
_CONFIG_HOME = resolve_xdg_home("XDG_CONFIG_HOME", Path.home() / ".config")
_DATA_HOME = resolve_xdg_home("XDG_DATA_HOME", Path.home() / ".local" / "share")

CONFIG_DIR = _CONFIG_HOME / "openbuds"
CONFIG_FILE = CONFIG_DIR / "config.toml"

# Directorio para datos de runtime (historial, estado, caches).
DATA_DIR = _DATA_HOME / "openbuds"

# Directorio para backups generados por la app (config WirePlumber, etc.).
BACKUP_DIR = DATA_DIR / "backups"

# Sección TOML bajo la que viven los ajustes (espacio de nombres propio).
_SECTION = "openbuds"

# Lista canónica de campos del AppConfig: (clave TOML, tipo esperado).
_FIELDS: tuple[tuple[str, type], ...] = (
    ("log_level", str),
    ("log_file", str),
    ("backup_dir", str),
    ("auto_rollback_on_error", bool),
    ("experimental_features", bool),
)


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Ajustes de la aplicación cargados desde el archivo de configuración.

    Atributos:
        log_level: Nivel de logging ("DEBUG", "INFO", "WARNING", ...).
        log_file: Ruta al archivo de log, o vacío para solo stderr.
        backup_dir: Directorio donde se guardan los backups.
        auto_rollback_on_error: Si se revierte automáticamente ante errores.
        experimental_features: Si se habilitan funciones de laboratorio.
    """

    log_level: str = "INFO"
    log_file: str = ""
    backup_dir: str = str(BACKUP_DIR)
    auto_rollback_on_error: bool = True
    experimental_features: bool = False


def default_config() -> AppConfig:
    """Devuelve la configuración con valores por defecto."""
    return AppConfig()


def load_config(path: Path = CONFIG_FILE) -> AppConfig:
    """Carga la configuración desde ``path``; usa defaults si no existe.

    Realiza un merge: los campos presentes en el TOML pisan los defaults; los
    ausentes conservan el valor por defecto.

    Args:
        path: Ruta al archivo TOML de configuración.

    Returns:
        AppConfig con los valores efectivos.

    Raises:
        ConfigError: Si el archivo existe pero el TOML está malformado, o si
            un valor tiene un tipo inesperado.

    """
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        return default_config()
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Config TOML malformado en {path}: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"No se pudo leer la config en {path}: {exc}") from exc

    section = data.get(_SECTION, {})
    if not isinstance(section, dict):
        raise ConfigError(
            f"La sección [{_SECTION}] debe ser una tabla, no {type(section).__name__}"
        )

    # Solo se leen los campos conocidos; se ignora el resto sin error (forward-compat).
    kwargs: dict[str, object] = {}
    for key, expected_type in _FIELDS:
        if key in section:
            value = section[key]
            if not isinstance(value, expected_type):
                raise ConfigError(
                    f"Campo '{key}' debe ser {expected_type.__name__}, no {type(value).__name__}"
                )
            kwargs[key] = value

    return AppConfig(**kwargs)  # type: ignore[arg-type]


def render_config_toml(config: AppConfig) -> str:
    """Render an ``AppConfig`` as readable TOML without writing it."""
    return f"""\
# Configuración de OpenBuds Manager.
# Edita manualmente si lo necesitas; los valores se recargan al iniciar la app.

[openbuds]
# Nivel de logging: DEBUG, INFO, WARNING, ERROR, CRITICAL.
log_level = {_toml_string(config.log_level)}

# Archivo de log (vacío = solo salida stderr). Se aplica rotación automática.
log_file = {_toml_string(config.log_file)}

# Directorio donde se guardan los backups de configuración del sistema.
backup_dir = {_toml_string(config.backup_dir)}

# Revierte automáticamente cualquier cambio si la verificación falla.
auto_rollback_on_error = {"true" if config.auto_rollback_on_error else "false"}

# Habilita funciones experimentales inestables (laboratorio).
experimental_features = {"true" if config.experimental_features else "false"}
"""


def backup_config_file(
    path: Path = CONFIG_FILE,
    backup_dir: Path = BACKUP_DIR,
) -> Path:
    """Create an atomic, timestamped backup of an existing configuration file."""
    backup_path = backup_dir / f"config.{_utc_timestamp()}.bak"
    try:
        content = path.read_bytes()
        _atomic_write_bytes(backup_path, content)
    except OSError as exc:
        raise ConfigError(f"Could not create configuration backup for {path}: {exc}") from exc
    return backup_path


def restore_config_file(backup_path: Path, path: Path = CONFIG_FILE) -> None:
    """Restore a valid TOML backup atomically and verify the installed file."""
    try:
        if not backup_path.is_file():
            raise ConfigError(f"Configuration backup does not exist: {backup_path}")
        load_config(backup_path)
        content = backup_path.read_bytes()
        _atomic_write_bytes(path, content)
    except ConfigError:
        raise
    except OSError as exc:
        raise ConfigError(f"Could not restore configuration from {backup_path}: {exc}") from exc

    try:
        load_config(path)
    except ConfigError as exc:
        raise ConfigError(f"Restored configuration could not be verified at {path}: {exc}") from exc


def save_config(
    config: AppConfig,
    path: Path = CONFIG_FILE,
    *,
    backup_dir: Path | None = None,
    auto_rollback: bool = True,
    dry_run: bool = False,
) -> Path | str | None:
    """Save configuration with backup, verification, rollback, and dry-run support.

    A normal save creates a timestamped backup before replacing an existing
    file, verifies the resulting TOML, and automatically restores that backup
    when verification fails. A dry-run only renders and returns the TOML string.

    Returns:
        The created backup path, ``None`` when there was no previous file, or
        the rendered TOML string in dry-run mode.

    Raises:
        ConfigError: If backup, writing, verification, or rollback fails.

    """
    content = render_config_toml(config)
    if dry_run:
        return content

    previous_backup: Path | None = None
    if path.exists():
        try:
            previous_backup = backup_config_file(path, backup_dir or BACKUP_DIR)
        except ConfigError:
            raise
        except OSError as exc:
            raise ConfigError(f"Could not create configuration backup for {path}: {exc}") from exc

    try:
        _atomic_write_bytes(path, content.encode("utf-8"))
    except OSError as exc:
        raise ConfigError(f"Could not write configuration at {path}: {exc}") from exc

    try:
        load_config(path)
    except ConfigError as exc:
        if previous_backup is not None and auto_rollback:
            try:
                _restore_file_atomically(previous_backup, path)
            except OSError as rollback_exc:
                raise ConfigError(
                    f"Configuration verification failed at {path}; automatic rollback failed: "
                    f"{rollback_exc}"
                ) from rollback_exc
            raise ConfigError(
                f"Configuration verification failed at {path}; automatic rollback applied"
            ) from exc

        if previous_backup is None:
            detail = "no previous backup was available"
        else:
            detail = "automatic rollback is disabled"
        raise ConfigError(f"Configuration verification failed at {path}; {detail}") from exc

    return previous_backup


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


def _restore_file_atomically(backup_path: Path, path: Path) -> None:
    """Restore bytes from a backup without consuming the backup file."""
    _atomic_write_bytes(path, backup_path.read_bytes())


def _utc_timestamp() -> str:
    """Return the filename timestamp used by versioned backups."""
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def _render_toml(config: AppConfig) -> str:
    """Compatibility wrapper for the public TOML renderer."""
    return render_config_toml(config)


def _toml_string(value: str) -> str:
    """Devuelve un TOML basic string usando escapes compatibles con JSON."""
    return json.dumps(value, ensure_ascii=False)
