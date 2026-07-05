"""Modelo de información del entorno del sistema."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SystemInfo:
    """Información del entorno del sistema operativo y del stack de audio.

    Recopilada por ``infrastructure.system.environment_detector`` antes de
    cualquier modificación (política de seguridad del proyecto).

    Atributos:
        os_id: Identificador del SO (p. ej. "ubuntu").
        os_version: Versión del SO (p. ej. "24.04").
        kernel_version: Versión del kernel Linux.
        bluez_version: Versión de BlueZ (p. ej. "5.72").
        pipewire_version: Versión de libpipewire (p. ej. "1.0.5").
        wireplumber_version: Versión de WirePlumber (p. ej. "0.4.17").
        wireplumber_config_style: Estilo de configuración ("lua-0.4" o "conf-0.5").
            Crítico: Ubuntu 24.04 usa "lua-0.4".
        dbus_version: Versión del daemon D-Bus / systemd.
        has_bluetooth_adapter: Si se detectó al menos un adaptador Bluetooth.
        is_supported: Si el entorno cumple los requisitos mínimos del proyecto.
    """

    os_id: str
    os_version: str
    kernel_version: str
    bluez_version: str
    pipewire_version: str
    wireplumber_version: str
    wireplumber_config_style: str
    dbus_version: str
    has_bluetooth_adapter: bool
    is_supported: bool
