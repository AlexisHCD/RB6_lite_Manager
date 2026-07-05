"""Contrato del repositorio de configuración del sistema (WirePlumber).

Implementación de referencia: ``openbuds.infrastructure.wireplumber.config_editor``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConfigBackup:
    """Referencia a un backup de configuración creado antes de un cambio.

    Atributos:
        backup_path: Ruta absoluta al archivo de backup (timestamped).
        original_path: Ruta del archivo original modificado.
        created_at: Marca temporal ISO-8601 UTC de la creación.
    """

    backup_path: str
    original_path: str
    created_at: str


class IConfigRepository:
    """Lectura y escritura segura de configuración de WirePlumber.

    POLÍTICA DE SEGURIDAD (ver ADR-0002 y docs/RESTRICTIONES.md):
      1. Solo se escriben overrides en ``~/.config/wireplumber/`` (por usuario).
         Nunca en ``/usr/share/`` ni con root.
      2. Todo cambio va precedido de un backup con timestamp.
      3. Todo cambio debe ser reversible (rollback).

    Sintaxis: Ubuntu 24.04 usa WirePlumber 0.4.x (Lua ``.lua.d/``).
    """

    def read_override(self, relative_path: str) -> str:
        """Lee el contenido de un override de configuración del usuario.

        Args:
            relative_path: Ruta relativa dentro de ``~/.config/wireplumber/``.

        """
        raise NotImplementedError

    def write_override(self, relative_path: str, content: str) -> ConfigBackup:
        """Escribe un override de configuración de forma segura.

        Crea un backup del archivo existente (si lo hay) antes de escribir.

        Returns:
            Referencia al backup creado (para rollback posterior).

        """
        raise NotImplementedError

    def restore_from_backup(self, backup: ConfigBackup) -> None:
        """Restaura la configuración desde un backup previo.

        Revierte exactamente el cambio asociado al backup dado.
        """
        raise NotImplementedError

    def list_backups(self) -> list[ConfigBackup]:
        """Lista los backups disponibles, del más reciente al más antiguo."""
        raise NotImplementedError
