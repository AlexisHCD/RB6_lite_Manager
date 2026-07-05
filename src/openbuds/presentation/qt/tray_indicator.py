"""Icono de bandeja del sistema (AppIndicator para GNOME).

Muestra el estado de conexión y permite acceso rápido a las funciones
principales. Estado: Fase 1 — esqueleto. Implementación en Fase 6.

Nota: GNOME no incluye soporte nativo de tray; requiere una extensión tipo
AppIndicator (gnome-shell-extension-appindicator), comúnmente instalada en
Ubuntu 24.04. Se documenta como requisito en el README.
"""

from __future__ import annotations


class TrayIndicator:
    """Icono residente en la bandeja del sistema.

    Estado: Fase 1 — sin implementación.
    """

    def __init__(self) -> None:
        raise NotImplementedError("Fase 6 (Interfaz gráfica).")
