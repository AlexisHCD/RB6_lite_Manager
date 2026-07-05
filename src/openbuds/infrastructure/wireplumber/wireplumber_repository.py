"""Implementación de ``IConfigRepository`` sobre WirePlumber (0.4 Lua).

Coordina ``WirePlumberConfigEditor`` y ``BackupManager`` para cumplir el
contrato seguro de lectura/escritura/restauración de overrides.

Estado: Fase 1 — esqueleto. Implementación en Fase 4.
"""

from __future__ import annotations

from openbuds.domain.interfaces import IConfigRepository
from openbuds.domain.interfaces.config_repo import ConfigBackup


class WirePlumberRepository(IConfigRepository):
    """Repositorio de configuración seguro para WirePlumber 0.4.

    Estado: Fase 1 — sin implementación.
    """

    def read_override(self, relative_path: str) -> str:
        raise NotImplementedError("Fase 4 (Optimización).")

    def write_override(self, relative_path: str, content: str) -> ConfigBackup:
        raise NotImplementedError("Fase 4 (Optimización).")

    def restore_from_backup(self, backup: ConfigBackup) -> None:
        raise NotImplementedError("Fase 4 (Optimización).")

    def list_backups(self) -> list[ConfigBackup]:
        raise NotImplementedError("Fase 4 (Optimización).")
