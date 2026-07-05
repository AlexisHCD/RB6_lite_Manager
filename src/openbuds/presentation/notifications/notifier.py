"""Notificador de escritorio.

Envía notificaciones al usuario (conexión/desconexión, fin de Health Check,
revertido automático). En GNOME se usa la interfaz ``org.freedesktop.Notifications``
(FreeDesktop notifications) vía D-Bus.

Estado: Fase 1 — esqueleto. Implementación en Fase 6.
"""

from __future__ import annotations


class DesktopNotifier:
    """Envoltorio sobre freedesktop Notifications.

    Estado: Fase 1 — sin implementación.
    """

    def notify(self, summary: str, body: str = "") -> None:
        """Muestra una notificación de escritorio."""
        raise NotImplementedError("Fase 6 (Interfaz gráfica).")
