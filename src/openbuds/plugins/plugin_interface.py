"""Contrato base para plugins de OpenBuds (Fase 8).

Un plugin puede:
  - Registrar nuevos perfiles de dispositivo.
  - Aportar comandos de diagnóstico adicionales.
  - Aportar vistas de laboratorio experimental.

Estado: Fase 1 — contrato definido, sin mecanismo de carga/registro.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class OpenBudsPlugin(Protocol):
    """Contrato que todo plugin debe satisfacer.

    El sistema de carga (Fase 8) descubrirá entry points o módulos y los
    instanciará; este Protocol define la forma esperada.
    """

    @property
    def plugin_id(self) -> str:
        """Identificador estable del plugin."""
        ...

    @property
    def display_name(self) -> str:
        """Nombre legible para mostrar en la UI."""
        ...

    def activate(self) -> None:
        """Inicializa el plugin (registra perfiles, hooks, etc.)."""
        ...

    def deactivate(self) -> None:
        """Limpia recursos al descargar el plugin."""
        ...
