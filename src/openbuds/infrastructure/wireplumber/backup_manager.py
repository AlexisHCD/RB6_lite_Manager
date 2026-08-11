"""Gestor de backups timestamped para cambios de configuración.

Centraliza la creación y restauración de backups. Si la creación del backup
falla, el cambio NO se aplica (lanza ``BackupError``): es invariante de
seguridad del proyecto.

Estado: Etapa 0 — esqueleto. Implementación pendiente de la Etapa 5.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path


def timestamp() -> str:
    """Devuelve un timestamp UTC compacto y seguro para nombres de archivo.

    Formato: ``YYYYmmdd_HHMMSS_ffffff`` (microsegundos) para evitar colisiones.
    """
    return datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S_%f")


class BackupManager:
    """Crea y restaura backups de archivos de configuración.

    Estado: Etapa 0 — sin implementación.

    Invariante: ``create_backup`` devuelve una ruta válida o lanza
    ``BackupError``. Nunca devuelve None silenciosamente.
    """

    def __init__(self, backup_dir: Path) -> None:
        self._backup_dir = backup_dir

    def create_backup(self, source: Path) -> Path:
        """Crea una copia timestamped de ``source`` y devuelve su ruta.

        Lanza ``BackupError`` si no se puede crear. Si ``source`` no existe,
        devuelve una ruta "marker" que indica que el original estaba ausente
        (para que restore sepa eliminar el override en lugar de restaurar).
        """
        raise NotImplementedError("Implementación pendiente de la Etapa 5 (backup y rollback).")

    def list_backups(self) -> list[Path]:
        """Lista los backups disponibles, del más reciente al más antiguo."""
        raise NotImplementedError("Implementación pendiente de la Etapa 5 (backup y rollback).")

    def restore(self, backup_path: Path) -> None:
        """Restaura el original desde ``backup_path``."""
        raise NotImplementedError("Implementación pendiente de la Etapa 5 (backup y rollback).")
