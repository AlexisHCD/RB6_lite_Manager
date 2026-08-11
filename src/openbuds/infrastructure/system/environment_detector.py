"""Detector del entorno del sistema (SO, kernel, versiones del stack, permisos).

Ejecuta la fase OBLIGATORIA de "detectar entorno" antes de cualquier
modificación (política de seguridad del proyecto). Si el entorno no cumple los
requisitos mínimos, las operaciones de escritura se abortan.

Estado: detección completa del entorno base (solo lectura).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from openbuds.domain.models import SystemInfo


def _run(args: list[str], timeout: float = 5.0) -> str:
    """Ejecuta un comando de solo lectura y devuelve su stdout (sin errores)."""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _run_succeeds(args: list[str], timeout: float = 5.0) -> bool:
    """Comprueba el estado de un comando de solo lectura sin usar su salida."""
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False
    return result.returncode == 0


def _parse_version(output: str, component: str) -> str:
    """Extrae una versión semántica de la salida de una herramienta."""
    match = re.search(rf"(?:lib{component}\s+)?(\d+\.\d+(?:\.\d+)?)", output)
    return match.group(1) if match else "unknown"


def _parse_bluez_version(output: str) -> str:
    """Extrae la versión de BlueZ desde ``bluetoothctl --version``."""
    return _parse_version(output, "bluez")


def _parse_pipewire_version(output: str) -> str:
    """Extrae la versión compilada de PipeWire sin asumir una versión."""
    return _parse_version(output, "pipewire")


def _parse_wireplumber_version(output: str) -> str:
    """Extrae la versión de WirePlumber desde sus salidas conocidas."""
    return _parse_version(output, "wireplumber")


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
    match = re.fullmatch(r"(\d+)\.(\d+)(?:\.\d+)?", version)
    if not match:
        return "unknown"
    major, minor = int(match.group(1)), int(match.group(2))
    return "lua-0.4" if (major, minor) < (0, 5) else "conf-0.5"


def _has_bluetooth_adapter(sysfs_path: Path = Path("/sys/class/bluetooth")) -> bool:
    """Devuelve si sysfs contiene al menos una entrada de adaptador ``hci*``."""
    try:
        return any(entry.name.startswith("hci") for entry in sysfs_path.iterdir())
    except OSError:
        return False


def _is_user_config_writable(config_path: Path | None = None) -> bool:
    """Comprueba escritura/descenso en la ruta existente más cercana, sin crearla."""
    if config_path is None:
        config_path = Path.home() / ".config" / "openbuds"
    candidate = config_path
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    if not candidate.is_dir():
        return False
    return os.access(candidate, os.W_OK | os.X_OK)


def _is_system_supported(info: SystemInfo) -> bool:
    """Evalúa los requisitos de compatibilidad del sistema y del stack."""
    return all(
        (
            info.os_id == "ubuntu" and info.os_version.startswith("24.04"),
            info.bluez_version != "unknown",
            info.pipewire_version != "unknown",
            info.wireplumber_version != "unknown",
            info.wireplumber_config_style == "lua-0.4",
            info.system_bus_available,
        )
    )


def is_runtime_ready() -> bool:
    """Indica si el intérprete puede usar el runtime Gio del sistema."""
    try:
        if Path(sys.base_prefix).resolve() != Path("/usr"):
            return False
        import gi

        gi.require_version("Gio", "2.0")
        from gi.repository import Gio, GLib

        _ = Gio, GLib
    except (ImportError, ValueError, OSError):
        return False
    return True


def detect() -> SystemInfo:
    """Detecta y devuelve la información del entorno.

    La función solo ejecuta comandos de consulta y lecturas de sysfs/configuración.
    """
    os_id, os_version = _detect_os()
    kernel = _run(["uname", "-r"])
    # bluetoothctl --version imprime "bluetoothctl: 5.72"; nos quedamos con el nº.
    bluez_raw = _run(["bluetoothctl", "--version"])
    bluez_version = _parse_bluez_version(bluez_raw)
    # pw-dump --version no existe; pipewire --version sí (tres líneas).
    pipewire_version = "unknown"
    if shutil.which("pipewire"):
        pw_raw = _run(["pipewire", "--version"])
        pipewire_version = _parse_pipewire_version(pw_raw)

    wp_raw = _run(["wireplumber", "--version"])
    wireplumber_version = _parse_wireplumber_version(wp_raw)
    if wireplumber_version == "unknown":
        for package in ("wireplumber-0.4", "wireplumber-0.5"):
            wireplumber_version = _parse_wireplumber_version(
                _run(["pkg-config", "--modversion", package])
            )
            if wireplumber_version != "unknown":
                break

    style = _detect_wp_config_style(wireplumber_version)
    dbus_raw = _run(["busctl", "--version"])
    dbus_version = dbus_raw.splitlines()[0] if dbus_raw else "unknown"
    system_bus_available = _run_succeeds(["busctl", "--system", "list", "--no-pager"])
    has_bluetooth_adapter = _has_bluetooth_adapter()
    user_config_writable = _is_user_config_writable()

    info = SystemInfo(
        os_id=os_id,
        os_version=os_version,
        kernel_version=kernel,
        bluez_version=bluez_version,
        pipewire_version=pipewire_version,
        wireplumber_version=wireplumber_version,
        wireplumber_config_style=style,
        dbus_version=dbus_version,
        has_bluetooth_adapter=has_bluetooth_adapter,
        system_bus_available=system_bus_available,
        user_config_writable=user_config_writable,
        is_supported=False,
    )
    return replace(info, is_supported=_is_system_supported(info))
