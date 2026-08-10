"""Configuración de logging estructurado y puente de eventos para la UI.

Punto único de configuración para todo el proyecto, con formato consistente y
rotación de archivos para evitar crecimiento indefinido en disco.

Diseño:
  - Salida stderr siempre (para desarrollo y diagnósticos rápidos).
  - Archivo opcional con ``RotatingFileHandler`` (1 MiB por archivo, 5 backups).
  - Formato legible en una línea.
  - Publicación opcional de registros como DTOs inmutables en ``EventBus`` para
    que la vista de Logs pueda suscribirse sin recibir ``LogRecord`` mutables.

La función ``setup_logging_from_config`` actúa de puente entre ``AppConfig`` y
``setup_logging``, de modo que el resto de la app solo necesita el config.
"""

from __future__ import annotations

import logging
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler

from openbuds.core.config import AppConfig
from openbuds.core.events import Event, EventBus, default_bus

FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S"

# Parámetros de rotación. 1 MiB * 6 ≈ 6 MiB máximo en disco por archivo de log.
_MAX_BYTES = 1 * 1024 * 1024
_BACKUP_COUNT = 5
LOG_EVENT_NAME = "log.recorded"


@dataclass(frozen=True, slots=True)
class LogEntry:
    """Representación inmutable y segura para UI de un registro de logging.

    ``timestamp`` siempre es consciente de zona horaria y está expresado en
    UTC, derivado del instante de creación del ``LogRecord``.
    """

    timestamp: datetime
    level_name: str
    logger_name: str
    message: str
    exception_text: str | None = None


class EventBusLogHandler(logging.Handler):
    """Publica registros de logging como eventos tipados en un ``EventBus``."""

    def __init__(self, event_bus: EventBus) -> None:
        super().__init__()
        self._event_bus = event_bus

    def emit(self, record: logging.LogRecord) -> None:
        """Convierte y publica un registro sin propagar fallos de suscriptores."""
        exception_text = None
        if record.exc_info:
            exception_text = logging.Formatter().formatException(record.exc_info)

        entry = LogEntry(
            timestamp=datetime.fromtimestamp(record.created, tz=UTC),
            level_name=record.levelname,
            logger_name=record.name,
            message=record.getMessage(),
            exception_text=exception_text,
        )
        try:
            self._event_bus.publish(Event(LOG_EVENT_NAME, entry))
        except Exception:
            # El logging no debe romper al llamador por un subscriber defectuoso.
            with suppress(Exception):
                self.handleError(record)


def get_logger(name: str) -> logging.Logger:
    """Devuelve un logger nombrado según la jerarquía del paquete.

    Se recomienda llamar como ``get_logger(__name__)`` al inicio de cada módulo.
    """
    return logging.getLogger(name)


def setup_logging(
    level: str = "INFO",
    log_file: str = "",
    event_bus: EventBus | None = None,
) -> None:
    """Configura el logging raíz del proyecto.

    Args:
        level: Nivel de logging ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL").
        log_file: Ruta a archivo de log. Vacío = solo stderr. Si se indica, se
            usa ``RotatingFileHandler`` con rotación automática.
        event_bus: Bus donde publicar los registros para la vista de Logs. Si es
            ``None``, se usa el bus global ``default_bus``.

    """
    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        EventBusLogHandler(event_bus or default_bus),
    ]
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


def setup_logging_from_config(
    config: AppConfig,
    event_bus: EventBus | None = None,
) -> None:
    """Configura el logging usando los campos de ``AppConfig``.

    Puente config -> logging. Típicamente se llama una vez al iniciar la app.

    Args:
        config: Configuración de la app; se usan ``log_level`` y ``log_file``.
        event_bus: Bus opcional para publicar registros; por defecto usa
            ``default_bus``.

    """
    setup_logging(level=config.log_level, log_file=config.log_file, event_bus=event_bus)


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
