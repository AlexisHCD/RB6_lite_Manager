"""Notificador de escritorio.

Envía notificaciones al usuario (conexión/desconexión, fin de Health Check,
revertido automático). En GNOME se usa la interfaz ``org.freedesktop.Notifications``
(FreeDesktop notifications) vía D-Bus.

Estado: Etapa 0 — esqueleto; notificaciones previstas después del MVP de la Etapa 3.
"""

from __future__ import annotations


class DesktopNotifier:
    """Envoltorio sobre freedesktop Notifications.

    Estado: Etapa 0 — sin implementación; prevista después del MVP de la Etapa 3.
    """

    def notify(self, summary: str, body: str = "") -> None:
        """Muestra una notificación de escritorio."""
        raise NotImplementedError("Implementación prevista después del MVP de la Etapa 3.")
