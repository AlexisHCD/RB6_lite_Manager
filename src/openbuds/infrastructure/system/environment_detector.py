"""Detector del entorno del sistema (SO, kernel, versiones del stack, permisos).

Ejecuta la fase OBLIGATORIA de "detectar entorno" antes de cualquier
modificación (política de seguridad del proyecto). Si el entorno no cumple los
requisitos mínimos, las operaciones de escritura se abortan.

Estado: Fase 1 — esqueleto con detección de versiones real (solo lectura).
La detección completa (permisos, adaptador, soporte) se completa en Fase 2/5.
"""

from __future__ import annotations

import shutil
import subprocess

from openbuds.domain.models import SystemInfo


def _run(args: list[str], timeout: float = 5.0) -> str:
    """Ejecuta un comando de solo lectura y devuelve su stdout (sin errores)."""
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return result.stdout.strip()


def _detect_os() -> tuple[str, str]:
    """Detecta (os_id, os_version) leyendo /etc/os-release (sin shell)."""
    os_id, os_version = "unknown", "unknown"
    try:
        with open("/etc/os-release", encoding="utf-8") as f:
            for line in f:
                if line.startswith("ID="):
                    os_id = line.split("=", 1)[1].strip().strip('"')
                elif line.startswith("VERSION_ID="):
                    os_version = line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return os_id, os_version


def _detect_wp_config_style(version: str) -> str:
    """Determina el estilo de configuración de WirePlumber desde su versión.

    Versión < 0.5  -> "lua-0.4"  (Ubuntu 24.04 = 0.4.17 -> este).
    Versión >= 0.5 -> "conf-0.5"
    """
    try:
        major = int(version.split(".")[0])
    except (ValueError, IndexError):
        return "unknown"
    return "conf-0.5" if major >= 1 else "lua-0.4"


def detect() -> SystemInfo:
    """Detecta y devuelve la información del entorno.

    Estado: Fase 1 — implementación parcial (versiones). Los campos
    ``has_bluetooth_adapter`` e ``is_supported`` se refinan en Fase 2/5.
    """
    os_id, os_version = _detect_os()
    kernel = _run(["uname", "-r"])
    # bluetoothctl --version imprime "bluetoothctl: 5.72"; nos quedamos con el nº.
    bluez_raw = _run(["bluetoothctl", "--version"])
    bluez_version = bluez_raw.split()[-1] if bluez_raw else "unknown"
    # pw-dump --version no existe; pipewire --version sí (tres líneas).
    pipewire_version = "unknown"
    if shutil.which("pipewire"):
        pw_raw = _run(["pipewire", "--version"])
        for line in pw_raw.splitlines():
            if line.startswith("Compiled with"):
                # "Compiled with libpipewire 1.0.5"
                pipewire_version = line.split()[-1]
                break

    # WirePlumber no soporta --version; se resuelve vía paquete o pkg-config.
    wireplumber_version = "unknown"
    wp_check = _run(["pkg-config", "--modversion", "libwireplumber-0.4"])
    if wp_check:
        wireplumber_version = wp_check

    style = _detect_wp_config_style(wireplumber_version)
    dbus_version = (
        _run(["busctl", "--version"]).splitlines()[0] if shutil.which("busctl") else "unknown"
    )

    return SystemInfo(
        os_id=os_id,
        os_version=os_version,
        kernel_version=kernel,
        bluez_version=bluez_version,
        pipewire_version=pipewire_version,
        wireplumber_version=wireplumber_version,
        wireplumber_config_style=style,
        dbus_version=dbus_version,
        has_bluetooth_adapter=False,  # TODO Fase 2: detectar vía BlueZ D-Bus.
        is_supported=os_id == "ubuntu" and os_version.startswith("24.04"),
    )
