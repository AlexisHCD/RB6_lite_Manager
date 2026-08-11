"""Implementación de ``IConfigRepository`` sobre WirePlumber (0.4 Lua).

Coordina ``WirePlumberConfigEditor`` y ``BackupManager`` para cumplir el
contrato seguro de lectura/escritura/restauración de overrides.

Estado: Etapa 0 — esqueleto. Implementación pendiente de la Etapa 5.
"""

from __future__ import annotations

from openbuds.domain.interfaces import IConfigRepository
from openbuds.domain.interfaces.config_repo import ConfigBackup


class WirePlumberRepository(IConfigRepository):
    """Repositorio de configuración seguro para WirePlumber 0.4.

    Estado: Etapa 0 — sin implementación.
    """

    def read_override(self, relative_path: str) -> str:
        raise NotImplementedError("Implementación pendiente de la Etapa 5 (persistencia).")

    def write_override(self, relative_path: str, content: str) -> ConfigBackup:
        raise NotImplementedError("Implementación pendiente de la Etapa 5 (persistencia).")

    def restore_from_backup(self, backup: ConfigBackup) -> None:
        raise NotImplementedError("Implementación pendiente de la Etapa 5 (persistencia).")

    def list_backups(self) -> list[ConfigBackup]:
        raise NotImplementedError("Implementación pendiente de la Etapa 5 (persistencia).")
