"""Configuración de la propia aplicación OpenBuds (no del sistema).

Distinguir de ``infrastructure.persistence`` (que persiste el estado de
runtime). Este módulo carga ajustes estáticos/del usuario desde un archivo de
configuración (TOML o JSON) en ``~/.config/openbuds/``.

Estado: Fase 1 define el contrato y la estructura; la carga/escritura se
implementa en Fase 2.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Directorio base de configuración del usuario (respeta XDG_CONFIG_HOME).
CONFIG_DIR = Path.home() / ".config" / "openbuds"
CONFIG_FILE = CONFIG_DIR / "config.toml"

# Directorio para datos de runtime (historial, estado, caches).
DATA_DIR = Path.home() / ".local" / "share" / "openbuds"

# Directorio para backups generados por la app (config WirePlumber, etc.).
BACKUP_DIR = DATA_DIR / "backups"


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

    TODO (Fase 2): implementar lectura TOML y merge con defaults.
    """
    raise NotImplementedError("Implementación diferida a Fase 2 (Backend base).")
