"""Entry point de la CLI ``openbuds``."""

from __future__ import annotations

import argparse
import re
import sys
import threading
from dataclasses import dataclass
from typing import Final

from openbuds import __version__
from openbuds.application.get_device_info import DeviceAggregate, GetDeviceInfoUseCase
from openbuds.application.scan_devices import ScanDevicesRequest, ScanDevicesUseCase
from openbuds.application.session_control import (
    ConnectDeviceRequest,
    ConnectDeviceUseCase,
    DisconnectDeviceRequest,
    DisconnectDeviceUseCase,
    SetAudioProfileRequest,
    SetAudioProfileUseCase,
)
from openbuds.application.watch_devices import WatchDevicesUseCase
from openbuds.core.config import CONFIG_FILE, AppConfig, load_config
from openbuds.core.errors import OpenBudsError
from openbuds.core.logging_setup import get_logger, setup_logging_from_config
from openbuds.domain.enums import BluetoothProfile, DeviceChangeKind
from openbuds.domain.models import DeviceChangeEvent, DeviceInfo
from openbuds.infrastructure.system import environment_detector
from openbuds.presentation.formatting import (
    REDACT_ADDRESS,
    connection_label,
    device_display_name,
    format_aggregate,
    sanitize_display_field,
)

_LOGGER = get_logger(__name__)
_BOOTSTRAP_COMMANDS: Final = frozenset(
    {
        "doctor",
        "config",
        "devices",
        "status",
        "watch",
        "connect",
        "disconnect",
        "music",
        "mic",
        "gui",
    }
)
_ADAPTER_NAME = re.compile(r"hci[0-9]+")
_ADDRESS = REDACT_ADDRESS


class _ConfirmationCancelledError(Exception):
    """Internal control flow for a user-declined action."""


@dataclass(frozen=True, slots=True)
class CliContext:
    """Dependencias efectivas disponibles para un handler de la CLI."""

    config: AppConfig | None = None
    scan_devices_use_case: ScanDevicesUseCase | None = None
    get_device_info_use_case: GetDeviceInfoUseCase | None = None
    watch_devices_use_case: WatchDevicesUseCase | None = None
    connect_use_case: ConnectDeviceUseCase | None = None
    disconnect_use_case: DisconnectDeviceUseCase | None = None
    set_audio_profile_use_case: SetAudioProfileUseCase | None = None


def _cmd_doctor(_context: CliContext) -> int:
    """Diagnostica compatibilidad del sistema, runtime y hardware disponible."""
    info = environment_detector.detect()
    runtime_ready = environment_detector.is_runtime_ready()
    print(f"SO:              {info.os_id} {info.os_version}")
    print(f"Kernel:          {info.kernel_version}")
    print(f"BlueZ:           {info.bluez_version}")
    print(f"PipeWire:        {info.pipewire_version}")
    print(f"WirePlumber:     {info.wireplumber_version} ({info.wireplumber_config_style})")
    print(f"D-Bus/systemd:   {info.dbus_version}")
    print(f"Bus del sistema:  {'sí' if info.system_bus_available else 'no'}")
    print(f"Configuración usuario: {'sí' if info.user_config_writable else 'no'}")
    print(f"Sistema soportado: {'SÍ' if info.is_supported else 'NO'}")
    print(f"Runtime aplicación: {'LISTO' if runtime_ready else 'NO LISTO'}")
    print(f"Hardware Bluetooth: {'disponible' if info.has_bluetooth_adapter else 'no disponible'}")
    return 0 if info.is_supported and runtime_ready else 1


def _cmd_config(context: CliContext) -> int:
    """Muestra la configuración efectiva sin persistirla."""
    if context.config is None:
        raise RuntimeError("configuración no disponible para el comando config")
    config = context.config
    log_file = config.log_file or "stderr"
    print(f"Nivel de log: {config.log_level}")
    print(f"Archivo de log: {log_file}")
    print(f"Directorio de backups: {config.backup_dir}")
    print(f"Auto rollback: {'sí' if config.auto_rollback_on_error else 'no'}")
    print(f"Funciones experimentales: {'sí' if config.experimental_features else 'no'}")
    print(f"CONFIG_FILE: {CONFIG_FILE}")
    return 0


def _cmd_gui(_context: CliContext) -> int:
    """Launch the Qt GUI; a graphical display is required."""
    from openbuds.presentation.qt.main_window import run_app

    return run_app()


def _cmd_devices(context: CliContext, args: argparse.Namespace) -> int:
    """Lista el snapshot de dispositivos Bluetooth en formato TSV."""
    if context.scan_devices_use_case is None:
        raise RuntimeError("caso de uso de dispositivos no disponible")

    devices = context.scan_devices_use_case.execute(
        ScanDevicesRequest(
            adapter_path=args.adapter,
            include_paired_only=args.paired_only,
        )
    )
    if not devices:
        print("No se encontraron dispositivos Bluetooth.")
        return 0

    print("NOMBRE\tCONEXIÓN\tEMPAREJAMIENTO\tADAPTADOR")
    for device in devices:
        print(_format_device(device))
    return 0


def _cmd_status(context: CliContext, args: argparse.Namespace) -> int:
    """Print aggregated state for paired Bluetooth devices."""
    if context.scan_devices_use_case is None or context.get_device_info_use_case is None:
        raise RuntimeError("casos de uso de estado no disponibles")
    devices = context.scan_devices_use_case.execute(
        ScanDevicesRequest(adapter_path=args.adapter, include_paired_only=True)
    )
    if not devices:
        print("No se encontraron dispositivos emparejados.")
        return 0

    for index, device in enumerate(devices):
        aggregate = context.get_device_info_use_case.execute(device.object_path)
        if aggregate is None:
            continue
        if index:
            print()
        print(_format_status(aggregate))
    return 0


def _resolve_device(
    scan_use_case: ScanDevicesUseCase,
    nombre: str | None,
    *,
    require_connected: bool,
) -> DeviceInfo | None:
    """Resolve a paired device by exact case-insensitive display name."""
    devices = scan_use_case.execute(ScanDevicesRequest(include_paired_only=True))
    if nombre is None:
        for device in devices:
            if device.connected:
                return device
        raise OpenBudsError("ningún dispositivo conectado")

    target = nombre.lower()
    matches = [
        device for device in devices if target in (device.alias.lower(), device.name.lower())
    ]
    safe_name = _sanitize_display_field(nombre)
    if not matches:
        raise OpenBudsError(f"dispositivo no encontrado: {safe_name}")
    if len(matches) > 1:
        raise OpenBudsError(f"nombre ambiguo: {safe_name}")
    device = matches[0]
    if require_connected and not device.connected:
        raise OpenBudsError(f"dispositivo no está conectado: {safe_name}")
    return device


def _confirm(action: str, yes: bool) -> None:
    """Require explicit confirmation unless ``--yes`` was provided."""
    if yes:
        return
    try:
        response = input(f"{action} [s/N]: ")
    except EOFError as exc:
        raise OpenBudsError("confirmación requerida; usa --yes en modo no interactivo") from exc
    if response.strip().casefold() not in {"s", "y", "sí", "si"}:
        print("Cancelado.")
        raise _ConfirmationCancelledError


def _device_display_name(device: DeviceInfo) -> str:
    """Return a privacy-safe display name for a device."""
    return device_display_name(device)


def _cmd_connect(context: CliContext, args: argparse.Namespace) -> int:
    """Connect a paired device after explicit confirmation."""
    if context.scan_devices_use_case is None or context.connect_use_case is None:
        raise RuntimeError("casos de uso de conexión no disponibles")
    device = _resolve_device(
        context.scan_devices_use_case,
        args.dispositivo,
        require_connected=False,
    )
    if device is None:
        raise OpenBudsError("dispositivo no encontrado")
    name = _device_display_name(device)
    try:
        _confirm(f"¿Conectar {name}?", args.yes)
    except _ConfirmationCancelledError:
        return 0
    context.connect_use_case.execute(ConnectDeviceRequest(device.object_path))
    print(f"Conectado: {name}")
    print("Recomendación: openbuds music para A2DP")
    return 0


def _cmd_disconnect(context: CliContext, args: argparse.Namespace) -> int:
    """Disconnect a connected device after explicit confirmation."""
    if context.scan_devices_use_case is None or context.disconnect_use_case is None:
        raise RuntimeError("casos de uso de desconexión no disponibles")
    device = _resolve_device(
        context.scan_devices_use_case,
        args.dispositivo,
        require_connected=True,
    )
    if device is None:
        raise OpenBudsError("dispositivo no encontrado")
    name = _device_display_name(device)
    try:
        _confirm(f"¿Desconectar {name}?", args.yes)
    except _ConfirmationCancelledError:
        return 0
    context.disconnect_use_case.execute(DisconnectDeviceRequest(device.object_path))
    print(f"Desconectado: {name}")
    return 0


def _cmd_music(context: CliContext, args: argparse.Namespace) -> int:
    """Select the offered runtime A2DP profile after confirmation."""
    if context.scan_devices_use_case is None or context.set_audio_profile_use_case is None:
        raise RuntimeError("casos de uso de audio no disponibles")
    device = _resolve_device(
        context.scan_devices_use_case,
        args.dispositivo,
        require_connected=True,
    )
    if device is None:
        raise OpenBudsError("dispositivo no encontrado")
    name = _device_display_name(device)
    try:
        _confirm(f"¿Activar Música (A2DP) en {name}?", args.yes)
    except _ConfirmationCancelledError:
        return 0
    context.set_audio_profile_use_case.execute(
        SetAudioProfileRequest(device.address, BluetoothProfile.A2DP)
    )
    print(f"Perfil A2DP aplicado a {name}")
    return 0


def _cmd_mic(context: CliContext, args: argparse.Namespace) -> int:
    """Select the offered runtime HFP profile after confirmation."""
    if context.scan_devices_use_case is None or context.set_audio_profile_use_case is None:
        raise RuntimeError("casos de uso de audio no disponibles")
    device = _resolve_device(
        context.scan_devices_use_case,
        args.dispositivo,
        require_connected=True,
    )
    if device is None:
        raise OpenBudsError("dispositivo no encontrado")
    name = _device_display_name(device)
    print(
        "Advertencia: activar el micrófono Bluetooth (HFP) puede reducir la calidad de "
        "reproducción."
    )
    try:
        _confirm(f"¿Activar Micrófono (HFP) en {name}?", args.yes)
    except _ConfirmationCancelledError:
        return 0
    context.set_audio_profile_use_case.execute(
        SetAudioProfileRequest(device.address, BluetoothProfile.HFP)
    )
    print(f"Perfil HFP aplicado a {name}")
    return 0


def _cmd_watch(
    context: CliContext,
    args: argparse.Namespace,
    stop: threading.Event | None = None,
) -> int:
    """Observe read-only Bluetooth device changes until interrupted."""
    if context.watch_devices_use_case is None:
        raise RuntimeError("caso de uso de watch no disponible")
    stop_event = stop if stop is not None else threading.Event()

    def _on_change(event: DeviceChangeEvent) -> None:
        if args.adapter is not None:
            device = event.current if event.current is not None else event.previous
            if device is None or device.adapter_path != args.adapter:
                return
        print(_format_watch_event(event), flush=True)

    unsubscribe = context.watch_devices_use_case.subscribe(_on_change)
    print("Observando cambios de dispositivos... (Ctrl+C para salir)", flush=True)
    try:
        while not stop_event.wait(0.2):
            pass
    except KeyboardInterrupt:
        pass
    finally:
        unsubscribe()
    print("Watch finalizado.", flush=True)
    return 0


def _device_connection_status(device: DeviceInfo) -> str:
    """Return the privacy-safe connection status used by status and watch."""
    return connection_label(device)


def _format_watch_event(event: DeviceChangeEvent) -> str:
    """Format a device event without MAC addresses or object paths."""
    device = event.current if event.current is not None else event.previous
    assert device is not None
    name = _sanitize_display_field(device.alias or device.name or "Dispositivo sin nombre")
    if event.kind is DeviceChangeKind.ADDED:
        return f"[apareció] {name}: {_device_connection_status(device)}"
    if event.kind is DeviceChangeKind.REMOVED:
        return f"[desapareció] {name}"

    status = _device_connection_status(device)
    connection_change = ""
    if event.previous is not None and event.current is not None:
        previous_status = _device_connection_status(event.previous)
        current_status = _device_connection_status(event.current)
        if event.current.connected != event.previous.connected:
            connection_change = f" (conexión: {previous_status} → {current_status})"
    return f"[cambio] {name}: {status}{connection_change}"


def _format_status(aggregate: DeviceAggregate) -> str:
    """Format an aggregate without displaying identifiers."""
    return format_aggregate(aggregate)


def _format_device(device: DeviceInfo) -> str:
    """Convierte un dispositivo en una fila TSV sin identificadores sensibles."""
    display_name = device_display_name(device)
    connection = connection_label(device)
    pairing = "emparejado" if device.paired else "no emparejado"
    adapter_name = device.adapter_path.rsplit("/", 1)[-1]
    adapter = adapter_name if _ADAPTER_NAME.fullmatch(adapter_name) else "desconocido"
    return "\t".join(
        (
            display_name,
            connection,
            pairing,
            _sanitize_display_field(adapter),
        )
    )


def _sanitize_display_field(value: str) -> str:
    """Sustituye caracteres no imprimibles y limita el campo a 80 caracteres."""
    return sanitize_display_field(value)


def _adapter_path(value: str) -> str:
    """Valida y normaliza un nombre de adaptador BlueZ."""
    prefix = "/org/bluez/"
    adapter_name = value[len(prefix) :] if value.startswith(prefix) else value
    if "/" in adapter_name or not _ADAPTER_NAME.fullmatch(adapter_name):
        raise argparse.ArgumentTypeError("ADAPTER debe ser hciN o /org/bluez/hciN")
    return f"{prefix}{adapter_name}"


def _build_scan_devices_use_case() -> ScanDevicesUseCase:
    """Compone el caso de uso y el repositorio BlueZ solo para ``devices``."""
    from openbuds.infrastructure.bluez.bluez_repository import BlueZRepository

    return ScanDevicesUseCase(BlueZRepository())


def _build_get_device_info_use_case() -> GetDeviceInfoUseCase:
    """Compose the read-only BlueZ and PipeWire repositories for ``status``."""
    from openbuds.infrastructure.bluez.bluez_repository import BlueZRepository
    from openbuds.infrastructure.pipewire.pipewire_repository import PipeWireRepository

    return GetDeviceInfoUseCase(BlueZRepository(), PipeWireRepository())


def _build_watch_devices_use_case() -> WatchDevicesUseCase:
    """Compose the read-only BlueZ repository for ``watch``."""
    from openbuds.infrastructure.bluez.bluez_repository import BlueZRepository

    return WatchDevicesUseCase(BlueZRepository())


def _build_session_use_cases() -> tuple[
    ConnectDeviceUseCase,
    DisconnectDeviceUseCase,
    SetAudioProfileUseCase,
    ScanDevicesUseCase,
]:
    """Compose the approved session use cases with lazy system adapters."""
    from openbuds.infrastructure.bluez.bluez_repository import BlueZRepository
    from openbuds.infrastructure.pipewire.pipewire_control_repository import (
        PipeWireControlRepository,
    )

    bluetooth = BlueZRepository()
    return (
        ConnectDeviceUseCase(bluetooth),
        DisconnectDeviceUseCase(bluetooth),
        SetAudioProfileUseCase(PipeWireControlRepository()),
        ScanDevicesUseCase(bluetooth),
    )


def _cmd_version(_context: CliContext) -> int:
    """Muestra la versión sin cargar configuración ni inicializar logging."""
    print(f"OpenBuds Manager {__version__}")
    return 0


def _cmd_future(command: str) -> int:
    """Informa del hito responsable de un comando aún no implementado."""
    milestones = {
        "codec": "Etapa 2 (sujeto a evidencia de la Etapa 1)",
        "health": "Etapa 4",
        "bench": "una etapa posterior",
    }
    print(
        f"El subcomando '{command}' aún no está implementado; "
        f"se implementará en {milestones[command]}.",
        file=sys.stderr,
    )
    return 2


def build_parser() -> argparse.ArgumentParser:
    """Construye el parser de la CLI sin ejecutar efectos secundarios."""
    parser = argparse.ArgumentParser(
        prog="openbuds",
        description="OpenBuds Manager — administrador de auriculares Bluetooth para Linux.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Diagnostica sistema, runtime y hardware Bluetooth.")
    sub.add_parser("config", help="Muestra la configuración efectiva.")
    sub.add_parser("gui", help="Abre la interfaz gráfica; requiere un display.")
    sub.add_parser("version", help="Muestra la versión de OpenBuds Manager.")
    devices = sub.add_parser("devices", help="Lista dispositivos Bluetooth.")
    devices.add_argument(
        "-p",
        "--paired-only",
        action="store_true",
        help="Muestra solo dispositivos emparejados.",
    )
    devices.add_argument(
        "-a",
        "--adapter",
        type=_adapter_path,
        help="Adaptador hciN o /org/bluez/hciN.",
    )
    status = sub.add_parser(
        "status", help="Muestra el estado agregado de los dispositivos emparejados."
    )
    status.add_argument(
        "-a",
        "--adapter",
        type=_adapter_path,
        help="Adaptador hciN o /org/bluez/hciN.",
    )
    watch = sub.add_parser(
        "watch", help="Observa en vivo los cambios de estado de los dispositivos emparejados."
    )
    watch.add_argument(
        "-a",
        "--adapter",
        type=_adapter_path,
        help="Adaptador hciN o /org/bluez/hciN.",
    )
    connect = sub.add_parser("connect", help="Conecta un dispositivo emparejado.")
    connect.add_argument("dispositivo", help="Alias o nombre exacto del dispositivo.")
    connect.add_argument("-y", "--yes", action="store_true", help="Omite la confirmación.")
    disconnect = sub.add_parser("disconnect", help="Desconecta un dispositivo conectado.")
    disconnect.add_argument("dispositivo", help="Alias o nombre exacto del dispositivo.")
    disconnect.add_argument("-y", "--yes", action="store_true", help="Omite la confirmación.")
    music = sub.add_parser("music", help="Activa el perfil A2DP runtime.")
    music.add_argument("dispositivo", nargs="?", help="Alias o nombre exacto del dispositivo.")
    music.add_argument("-y", "--yes", action="store_true", help="Omite la confirmación.")
    mic = sub.add_parser("mic", help="Activa el perfil HFP runtime.")
    mic.add_argument("dispositivo", nargs="?", help="Alias o nombre exacto del dispositivo.")
    mic.add_argument("-y", "--yes", action="store_true", help="Omite la confirmación.")
    sub.add_parser("codec", help="Muestra el códec activo.")
    sub.add_parser("health", help="Ejecuta un Health Check.")
    sub.add_parser("bench", help="Ejecuta un benchmark de enlace.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada principal de la CLI."""
    args = build_parser().parse_args(argv)
    command = args.command

    if command == "version":
        return _cmd_version(CliContext())
    if command not in _BOOTSTRAP_COMMANDS:
        return _cmd_future(command)

    logging_configured = False
    try:
        config = load_config()
        setup_logging_from_config(config)
        logging_configured = True
        if command == "devices":
            context = CliContext(
                config=config,
                scan_devices_use_case=_build_scan_devices_use_case(),
            )
            return _cmd_devices(context, args)
        if command == "status":
            context = CliContext(
                config=config,
                scan_devices_use_case=_build_scan_devices_use_case(),
                get_device_info_use_case=_build_get_device_info_use_case(),
            )
            return _cmd_status(context, args)
        if command == "watch":
            context = CliContext(
                config=config, watch_devices_use_case=_build_watch_devices_use_case()
            )
            return _cmd_watch(context, args)
        if command in {"connect", "disconnect", "music", "mic"}:
            connect_use_case, disconnect_use_case, set_profile_use_case, scan_use_case = (
                _build_session_use_cases()
            )
            context = CliContext(
                config=config,
                scan_devices_use_case=scan_use_case,
                connect_use_case=connect_use_case,
                disconnect_use_case=disconnect_use_case,
                set_audio_profile_use_case=set_profile_use_case,
            )
            handlers = {
                "connect": _cmd_connect,
                "disconnect": _cmd_disconnect,
                "music": _cmd_music,
                "mic": _cmd_mic,
            }
            return handlers[command](context, args)
        if command == "gui":
            return _cmd_gui(CliContext(config=config))
        context = CliContext(config=config)
        handler = _cmd_doctor if command == "doctor" else _cmd_config
        return handler(context)
    except OpenBudsError as exc:
        if logging_configured:
            _LOGGER.error("CLI error: %s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
