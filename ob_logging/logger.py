"""
Sistema de logging centralizado para OpenBuds Manager.

Todo el proyecto debe usar `get_logger(__name__)` en lugar de configurar
loggers manualmente. La configuración se define en un único lugar.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler  # noqa: A005 — stdlib shadow is intentional inside ob_logging
from pathlib import Path
from typing import Optional

_DEFAULT_LOG_DIR: Path = Path.home() / ".local" / "share" / "openbuds" / "logs"
_DEFAULT_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DEFAULT_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
_MAX_BYTES: int = 5 * 1024 * 1024  # 5 MB
_BACKUP_COUNT: int = 5

_configured: bool = False


def configure_logging(
    level: int = logging.DEBUG,
    log_dir: Optional[Path] = None,
    enable_console: bool = True,
    enable_file: bool = True,
) -> None:
    """
    Configura el logging raíz del proyecto. Debe llamarse una sola vez al inicio.

    Args:
        level: Nivel de logging (por defecto DEBUG para desarrollo).
        log_dir: Directorio donde guardar los logs. Si es None, usa el default.
        enable_console: Si True, imprime logs en stderr.
        enable_file: Si True, guarda logs en archivo rotativo.
    """
    global _configured
    if _configured:
        return

    root = logging.getLogger("openbuds")
    root.setLevel(level)

    formatter = logging.Formatter(_DEFAULT_FORMAT, datefmt=_DEFAULT_DATE_FORMAT)

    if enable_console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        root.addHandler(console_handler)

    if enable_file:
        target_dir = log_dir or _DEFAULT_LOG_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        log_file = target_dir / "openbuds.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        root.addHandler(file_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Obtiene un logger del proyecto. Usar siempre `get_logger(__name__)`.

    Args:
        name: Nombre del módulo (usar __name__).

    Returns:
        Logger configurado bajo el namespace 'openbuds'.
    """
    if name.startswith("openbuds."):
        return logging.getLogger(name)
    return logging.getLogger(f"openbuds.{name}")
