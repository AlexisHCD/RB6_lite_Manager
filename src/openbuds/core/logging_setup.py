"""Configuración de logging estructurado.

Proporciona un único punto de configuración para todo el proyecto, con
formato consistente y soporte opcional de archivo. Se diseña para integrarse
después con un handler de Qt (para la vista de Logs) sin acoplar aquí Qt.

Estado: Fase 1 define el contrato; la implementación completa (rotación,
formato JSON opcional) se completa en Fase 2.
"""

from __future__ import annotations

import logging

FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str) -> logging.Logger:
    """Devuelve un logger nombrado según la jerarquía del paquete.

    Se recomienda llamar como ``get_logger(__name__)`` al inicio de cada módulo.
    """
    return logging.getLogger(name)


def setup_logging(level: str = "INFO", log_file: str = "") -> None:
    """Configura el logging raíz del proyecto.

    Args:
        level: Nivel de logging ("DEBUG", "INFO", ...).
        log_file: Ruta a archivo de log. Vacío = solo stderr.

    TODO (Fase 2): añadir rotación (RotatingFileHandler), formato JSON opcional,
    y un handler puente hacia la vista de Logs en la GUI.

    """
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=level.upper(),
        format=FMT,
        datefmt=DATEFMT,
        handlers=handlers,
        force=True,
    )
