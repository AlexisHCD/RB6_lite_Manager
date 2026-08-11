"""Contrato reservado para plugins de OpenBuds en una etapa posterior.

No existe un mecanismo de carga o registro, ni se garantizan capacidades.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class OpenBudsPlugin(Protocol):
    """Forma reservada del contrato de plugin, sin mecanismo de carga asociado."""

    @property
    def plugin_id(self) -> str:
        """Identificador estable del plugin."""
        ...

    @property
    def display_name(self) -> str:
        """Nombre legible para mostrar en la UI."""
        ...

    def activate(self) -> None:
        """Activa el plugin según su implementación."""
        ...

    def deactivate(self) -> None:
        """Desactiva el plugin según su implementación."""
        ...
