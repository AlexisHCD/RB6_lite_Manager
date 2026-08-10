"""Editor seguro de configuración de WirePlumber (overrides por usuario).

POLÍTICA DE SEGURIDAD (ver ADR-0002 y docs/RESTRICTIONES.md):
  - Solo se opera bajo ``~/.config/wireplumber/`` (XDG_CONFIG_HOME).
  - NUNCA se escribe en ``/usr/share/wireplumber/`` (se sobrescribe al actualizar).
  - NUNCA se requiere root.
  - Todo cambio va precedido de backup con timestamp.
  - Todo cambio es reversible (rollback).

SINTAXIS: Ubuntu 24.04 = WirePlumber 0.4.x (Lua ``.lua.d/``).
Ejemplo de archivo override:
  ``bluetooth.lua.d/50-bluez-config.lua`` con bloque ``bluez_monitor.properties``.
NO usar la sintaxis 0.5 (``wireplumber.conf.d/*.conf``): rompería en Noble.

Estado: Fase 1 — esqueleto. Implementación en Fase 4.
"""

from __future__ import annotations

from pathlib import Path

# Ruta base de overrides del usuario (respeta XDG_CONFIG_HOME si está definido).
USER_CONFIG_DIR = Path.home() / ".config" / "wireplumber"


class WirePlumberConfigEditor:
    """Lectura y escritura segura de overrides de WirePlumber (sintaxis 0.4).

    Estado: Fase 1 — sin implementación.
    """

    def __init__(self, base_dir: Path = USER_CONFIG_DIR) -> None:
        self._base_dir = base_dir

    def read(self, relative_path: str) -> str:
        """Lee un override. Devuelve cadena vacía si no existe."""
        raise NotImplementedError("Fase 4 (Optimización).")

    def write(self, relative_path: str, content: str) -> str:
        """Escribe un override de forma segura (backup previo).

        Returns:
            Ruta absoluta del backup creado.

        """
        raise NotImplementedError("Fase 4 (Optimización).")

    def restore(self, backup_path: str, target_path: str) -> None:
        """Restaura ``target_path`` desde ``backup_path``."""
        raise NotImplementedError("Fase 4 (Optimización).")
