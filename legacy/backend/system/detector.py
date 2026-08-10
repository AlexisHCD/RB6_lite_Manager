"""
Detección del sistema operativo y componentes instalados.

Este módulo identifica la distribución Linux, versión del kernel,
y los componentes del stack Bluetooth/audio instalados en el sistema.
No modifica nada: es estrictamente de lectura.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ob_logging.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class DistroInfo:
    """Información de la distribución Linux."""

    name: str
    version: str
    id: str
    id_like: tuple[str, ...] = ()


@dataclass(frozen=True)
class KernelInfo:
    """Información del kernel."""

    release: str
    version: str
    machine: str


@dataclass(frozen=True)
class ComponentInfo:
    """Información de un componente del stack (BlueZ, PipeWire, etc.)."""

    name: str
    installed: bool
    version: Optional[str] = None
    executable: Optional[str] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class ServiceInfo:
    """Información de un servicio systemd."""

    name: str
    active: bool
    enabled: bool
    status: str


@dataclass(frozen=True)
class SystemReport:
    """Reporte completo del estado del sistema."""

    distro: DistroInfo
    kernel: KernelInfo
    bluez: ComponentInfo
    pipewire: ComponentInfo
    wireplumber: ComponentInfo
    bluetooth_service: ServiceInfo
    pipewire_service: ServiceInfo
    wireplumber_service: ServiceInfo
    bluetooth_adapters: list[str] = field(default_factory=list)
    codecs: list[str] = field(default_factory=list)
    python_version: str = ""


def _detect_distro() -> DistroInfo:
    """Detecta la distribución Linux leyendo /etc/os-release."""
    os_release = Path("/etc/os-release")
    data: dict[str, str] = {}

    if os_release.exists():
        for line in os_release.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, _, value = line.partition("=")
                data[key.strip()] = value.strip().strip('"')

    return DistroInfo(
        name=data.get("NAME", "Desconocida"),
        version=data.get("VERSION", "Desconocida"),
        id=data.get("ID", "unknown"),
        id_like=tuple(data.get("ID_LIKE", "").split()),
    )


def _detect_kernel() -> KernelInfo:
    """Detecta la versión del kernel."""
    return KernelInfo(
        release=platform.release(),
        version=platform.version(),
        machine=platform.machine(),
    )


def _get_command_version(executable: str, version_flag: str = "--version") -> Optional[str]:
    """
    Ejecuta un comando para obtener su versión.

    Args:
        executable: Nombre del binario (ej: 'bluetoothctl', 'pipewire').
        version_flag: Flag para obtener la versión.

    Returns:
        String con la versión o None si no se pudo obtener.
    """
    path = shutil.which(executable)
    if path is None:
        return None

    try:
        result = subprocess.run(
            [path, version_flag],
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = (result.stdout + result.stderr).strip()
        if not output:
            return None
        for line in output.splitlines():
            line = line.strip()
            if "Compiled with" in line or "Linked with" in line:
                parts = line.rsplit(" ", 1)
                if len(parts) == 2:
                    return parts[1]
            if line and line != executable and not line.startswith("/"):
                return line
        return output.splitlines()[0] if output else None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.debug("No se pudo obtener versión de %s: %s", executable, exc)
        return None


def _detect_component(name: str, executable: str, version_flag: str = "--version") -> ComponentInfo:
    """
    Detecta si un componente está instalado y obtiene su versión.

    Args:
        name: Nombre legible del componente.
        executable: Nombre del binario a buscar en PATH.
        version_flag: Flag para obtener la versión.

    Returns:
        ComponentInfo con el estado del componente.
    """
    path = shutil.which(executable)
    if path is None:
        logger.debug("Componente '%s' no encontrado (binario '%s' no en PATH)", name, executable)
        return ComponentInfo(name=name, installed=False, error=f"{executable} no encontrado en PATH")

    version = _get_command_version(executable, version_flag)
    logger.debug("Componente '%s' detectado: versión=%s, path=%s", name, version, path)
    return ComponentInfo(
        name=name,
        installed=True,
        version=version,
        executable=path,
    )


def _detect_service(service_name: str, user: bool = False) -> ServiceInfo:
    """
    Detecta el estado de un servicio systemd.

    Args:
        service_name: Nombre del servicio (ej: 'bluetooth.service').
        user: Si True, consulta servicios de usuario (--user).

    Returns:
        ServiceInfo con el estado del servicio.
    """
    systemctl_cmd = ["systemctl"]
    if user:
        systemctl_cmd.append("--user")

    try:
        is_active = subprocess.run(
            systemctl_cmd + ["is-active", "--quiet", service_name],
            capture_output=True,
            timeout=5,
        )
        active = is_active.returncode == 0

        is_enabled = subprocess.run(
            systemctl_cmd + ["is-enabled", "--quiet", service_name],
            capture_output=True,
            timeout=5,
        )
        enabled = is_enabled.returncode == 0

        status = "active (running)" if active else "inactive/stopped"

        return ServiceInfo(
            name=service_name,
            active=active,
            enabled=enabled,
            status=status,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.debug("No se pudo consultar servicio %s: %s", service_name, exc)
        return ServiceInfo(name=service_name, active=False, enabled=False, status=f"error: {exc}")


def detect_system() -> SystemReport:
    """
    Realiza una detección completa del sistema.

    No modifica nada. Es estrictamente de lectura.

    Returns:
        SystemReport con toda la información detectada.
    """
    logger.info("Iniciando detección del sistema...")

    distro = _detect_distro()
    kernel = _detect_kernel()
    bluez = _detect_component("BlueZ", "bluetoothctl", "version")
    pipewire = _detect_component("PipeWire", "pipewire", "--version")
    wireplumber = _detect_component("WirePlumber", "wireplumber", "--version")

    bluetooth_service = _detect_service("bluetooth.service")
    pipewire_service = _detect_service("pipewire.service", user=True)
    wireplumber_service = _detect_service("wireplumber.service", user=True)

    adapters = _detect_bluetooth_adapters()
    codecs = _detect_codecs()

    report = SystemReport(
        distro=distro,
        kernel=kernel,
        bluez=bluez,
        pipewire=pipewire,
        wireplumber=wireplumber,
        bluetooth_service=bluetooth_service,
        pipewire_service=pipewire_service,
        wireplumber_service=wireplumber_service,
        bluetooth_adapters=adapters,
        codecs=codecs,
        python_version=platform.python_version(),
    )

    logger.info("Detección completada: %s %s | kernel %s", distro.name, distro.version, kernel.release)
    return report


def _detect_bluetooth_adapters() -> list[str]:
    """
    Detecta los adaptadores Bluetooth presentes en el sistema.

    Returns:
        Lista con los nombres de interfaz de los adaptadores (ej: ['hci0']).
    """
    adapters: list[str] = []
    bluetooth_dir = Path("/sys/class/bluetooth")

    if not bluetooth_dir.exists():
        logger.debug("Directorio /sys/class/bluetooth no existe")
        return adapters

    for entry in bluetooth_dir.iterdir():
        if entry.name.startswith("hci"):
            adapters.append(entry.name)

    logger.debug("Adaptadores Bluetooth detectados: %s", adapters)
    return adapters


def _detect_codecs() -> list[str]:
    """
    Detecta los códecs Bluetooth disponibles en el sistema.

    Verifica la presencia de librerías de códecs y endpoints A2DP.

    Returns:
        Lista de nombres de códecs disponibles.
    """
    codecs: list[str] = []

    codec_libs: dict[str, str] = {
        "LDAC": "libldacbt_enc.so",
        "aptX": "libfreeaptx.so",
        "aptX-HD": "libaptxHD_encode.so",
        "AAC": "libldaacbt_enc.so",
    }

    lib_dirs = [
        Path("/usr/lib/x86_64-linux-gnu"),
        Path("/usr/lib"),
        Path("/usr/local/lib"),
    ]

    for codec_name, lib_file in codec_libs.items():
        for lib_dir in lib_dirs:
            if (lib_dir / lib_file).exists():
                codecs.append(codec_name)
                break

    if shutil.which("pipewire") is not None:
        try:
            result = subprocess.run(
                ["pw-dump"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            output = result.stdout.lower()
            for codec in ("sbc", "aac", "ldac", "aptx", "opus", "lc3", "faststream"):
                if codec in output and codec not in [c.lower() for c in codecs]:
                    codecs.append(codec.upper())
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

    if not codecs:
        codecs.append("SBC")

    logger.debug("Códecs detectados: %s", codecs)
    return codecs
