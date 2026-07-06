"""Configuración de la propia aplicación OpenBuds (no del sistema).

Distinguir de ``infrastructure.persistence`` (que persiste el estado de
runtime). Este módulo carga y guarda los ajustes estáticos del usuario desde
un archivo de configuración TOML en ``~/.config/openbuds/``.

Formato del archivo (escritura manual para preservar comentarios — ver ADR-0006):

    [openbuds]
    log_level = "INFO"
    log_file = ""
    backup_dir = "~/.local/share/openbuds/backups"
    auto_rollback_on_error = true
    experimental_features = false
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from openbuds.core.errors import ConfigError

# Directorio base de configuración del usuario (respeta XDG_CONFIG_HOME).
CONFIG_DIR = Path.home() / ".config" / "openbuds"
CONFIG_FILE = CONFIG_DIR / "config.toml"

# Directorio para datos de runtime (historial, estado, caches).
DATA_DIR = Path.home() / ".local" / "share" / "openbuds"

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
    if not path.exists():
        return default_config()

    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Config TOML malformado en {path}: {exc}") from exc

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


def save_config(config: AppConfig, path: Path = CONFIG_FILE) -> None:
    """Guarda la configuración en ``path`` en formato TOML con comentarios.

    La escritura es manual (sin ``tomli_w``) para poder incluir comentarios que
    documenten cada campo al usuario. Ver ADR-0006.

    Args:
        config: Configuración a guardar.
        path: Ruta de destino. Se crea el directorio padre si no existe.

    Raises:
        ConfigError: Si no se puede escribir el archivo (permisos, etc.).

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    content = _render_toml(config)
    try:
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"No se pudo escribir la config en {path}: {exc}") from exc


def _render_toml(config: AppConfig) -> str:
    """Serializa un AppConfig a TOML legible con comentarios."""
    return f"""\
# Configuración de OpenBuds Manager.
# Edita manualmente si lo necesitas; los valores se recargan al iniciar la app.

[openbuds]
# Nivel de logging: DEBUG, INFO, WARNING, ERROR, CRITICAL.
log_level = "{config.log_level}"

# Archivo de log (vacío = solo salida stderr). Se aplica rotación automática.
log_file = "{config.log_file}"

# Directorio donde se guardan los backups de configuración del sistema.
backup_dir = "{config.backup_dir}"

# Revierte automáticamente cualquier cambio si la verificación falla.
auto_rollback_on_error = {"true" if config.auto_rollback_on_error else "false"}

# Habilita funciones experimentales inestables (laboratorio).
experimental_features = {"true" if config.experimental_features else "false"}
"""
