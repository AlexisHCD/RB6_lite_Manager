"""Configuración de logging estructurado.

Punto único de configuración para todo el proyecto, con formato consistente y
rotación de archivos para evitar crecimiento indefinido en disco.

Diseño:
  - Salida stderr siempre (para desarrollo y diagnósticos rápidos).
  - Archivo opcional con ``RotatingFileHandler`` (1 MiB por archivo, 5 backups).
  - Formato legible en una línea (no JSON — se aplaza hasta que la vista de
    Logs de la GUI lo requiera, ver nota en ROADMAP).

La función ``setup_logging_from_config`` actúa de puente entre ``AppConfig`` y
``setup_logging``, de modo que el resto de la app solo necesita el config.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from openbuds.core.config import AppConfig

FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S"

# Parámetros de rotación. 1 MiB * 6 ≈ 6 MiB máximo en disco por archivo de log.
_MAX_BYTES = 1 * 1024 * 1024
_BACKUP_COUNT = 5


def get_logger(name: str) -> logging.Logger:
    """Devuelve un logger nombrado según la jerarquía del paquete.

    Se recomienda llamar como ``get_logger(__name__)`` al inicio de cada módulo.
    """
    return logging.getLogger(name)


def setup_logging(level: str = "INFO", log_file: str = "") -> None:
    """Configura el logging raíz del proyecto.

    Args:
        level: Nivel de logging ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL").
        log_file: Ruta a archivo de log. Vacío = solo stderr. Si se indica, se
            usa ``RotatingFileHandler`` con rotación automática.

    """
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        handlers.append(
            RotatingFileHandler(
                log_file,
                maxBytes=_MAX_BYTES,
                backupCount=_BACKUP_COUNT,
                encoding="utf-8",
            )
        )

    logging.basicConfig(
        level=_normalize_level(level),
        format=FMT,
        datefmt=DATEFMT,
        handlers=handlers,
        force=True,
    )


def setup_logging_from_config(config: AppConfig) -> None:
    """Configura el logging usando los campos de ``AppConfig``.

    Puente config -> logging. Típicamente se llama una vez al iniciar la app.

    Args:
        config: Configuración de la app; se usan ``log_level`` y ``log_file``.

    """
    setup_logging(level=config.log_level, log_file=config.log_file)


def _normalize_level(level: str) -> int | str:
    """Convierte un nivel en texto al valor numérico de ``logging``.

    Acepta el nombre en mayúsculas o minúsculas. Si no se reconoce, cae a INFO
    de forma segura (mejor log de más que logging roto).
    """
    name = level.strip().upper()
    numeric = logging.getLevelName(name)
    # logging.getLevelName devuelve int para niveles válidos, str para inválidos.
    if isinstance(numeric, int):
        return numeric
    # Nivel no reconocido: fallback seguro a INFO.
    return logging.INFO
