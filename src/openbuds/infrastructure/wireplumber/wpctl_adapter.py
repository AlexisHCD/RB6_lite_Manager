"""Adaptador de la CLI ``wpctl`` (WirePlumber).

Encapsula las invocaciones subprocess a ``wpctl`` para inspección y control de
ruteo/perfiles. Solo lectura + acciones de control (set-default, set-profile).

Estado: Fase 1 — esqueleto. Implementación en Fase 4.

Comandos relevantes (verificados en man pages / wpctl --help):
  - ``wpctl status``            -> resumen de audio/video (dispositivos, defaults).
  - ``wpctl inspect <id>``      -> propiedades detalladas de un objeto.
  - ``wpctl set-default <id>``  -> fija el dispositivo por defecto.
  - ``wpctl set-profile <id> <idx>`` -> cambia el perfil (a2dp-sink, headset-head-unit).
  - ``wpctl set-volume <id> <vol>``  -> ajusta volumen.

Recarga de configuración: tras editar archivos, reiniciar el servicio de usuario
``systemctl --user restart wireplumber`` (NO hay wpctl reload genérico).
"""

from __future__ import annotations


class WpctlAdapter:
    """Envoltorio subprocess sobre ``wpctl``.

    Estado: Fase 1 — sin implementación.
    """

    def status(self) -> str:
        """Devuelve la salida de ``wpctl status``."""
        raise NotImplementedError("Fase 4 (Optimización).")

    def inspect(self, node_id: int) -> str:
        """Devuelve la salida de ``wpctl inspect <node_id>``."""
        raise NotImplementedError("Fase 4 (Optimización).")

    def set_profile(self, device_id: int, profile_index: int) -> None:
        """Ejecuta ``wpctl set-profile <device_id> <profile_index>``."""
        raise NotImplementedError("Fase 4 (Optimización).")

    def restart_service(self) -> None:
        """Reinicia el servicio de usuario WirePlumber para releer configuración.

        Ejecuta ``systemctl --user restart wireplumber``.
        """
        raise NotImplementedError("Fase 4 (Optimización).")
