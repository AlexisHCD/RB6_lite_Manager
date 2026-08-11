"""Icono de bandeja del sistema (AppIndicator para GNOME).

Muestra el estado de conexión y permite acceso rápido a las funciones
principales. Estado: Etapa 0 — esqueleto; se prevé después del MVP de la Etapa 3.

Nota: GNOME no incluye soporte nativo de tray; requiere una extensión tipo
AppIndicator (gnome-shell-extension-appindicator), comúnmente instalada en
Ubuntu 24.04. Se documenta como requisito en el README.
"""

from __future__ import annotations


class TrayIndicator:
    """Icono residente en la bandeja del sistema.

    Estado: Etapa 0 — sin implementación; se prevé después del MVP de la Etapa 3.
    """

    def __init__(self) -> None:
        raise NotImplementedError("Implementación prevista después del MVP de la Etapa 3.")
