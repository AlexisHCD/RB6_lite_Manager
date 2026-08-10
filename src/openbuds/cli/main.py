"""Entry point de la CLI ``openbuds``.

Los comandos ``doctor`` y ``config`` son la base funcional de la Fase 2 y
comparten un bootstrap de configuración y logging. Los demás comandos están
registrados para ofrecer una interfaz estable, pero se implementan en sus
fases correspondientes.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Final

from openbuds import __version__
from openbuds.core.config import CONFIG_FILE, AppConfig, load_config
from openbuds.core.errors import OpenBudsError
from openbuds.core.logging_setup import get_logger, setup_logging_from_config
from openbuds.infrastructure.system import environment_detector

_LOGGER = get_logger(__name__)
_BOOTSTRAP_COMMANDS: Final = frozenset({"doctor", "config"})


@dataclass(frozen=True, slots=True)
class CliContext:
    """Dependencias efectivas disponibles para un handler de la CLI."""

    config: AppConfig | None = None


def _cmd_doctor(_context: CliContext) -> int:
    """Detecta el entorno y devuelve 0 si está soportado."""
    info = environment_detector.detect()
    print(f"SO:              {info.os_id} {info.os_version}")
    print(f"Kernel:          {info.kernel_version}")
    print(f"BlueZ:           {info.bluez_version}")
    print(f"PipeWire:        {info.pipewire_version}")
    print(f"WirePlumber:     {info.wireplumber_version} ({info.wireplumber_config_style})")
    print(f"D-Bus/systemd:   {info.dbus_version}")
    print(f"Bus del sistema:  {'sí' if info.system_bus_available else 'no'}")
    print(f"Configuración usuario: {'sí' if info.user_config_writable else 'no'}")
    print(f"Adaptador BT:    {'sí' if info.has_bluetooth_adapter else 'no detectado'}")
    print(f"Entorno soportado: {'SÍ' if info.is_supported else 'NO'}")
    return 0 if info.is_supported else 1


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


def _cmd_version(_context: CliContext) -> int:
    """Muestra la versión sin cargar configuración ni inicializar logging."""
    print(f"OpenBuds Manager {__version__}")
    return 0


def _cmd_future(command: str) -> int:
    """Informa de la fase responsable de un comando aún no implementado."""
    phases = {
        "devices": "Fase 3",
        "codec": "Fase 3/4",
        "health": "Fase 5",
        "bench": "Fase 5",
    }
    print(
        f"El subcomando '{command}' aún no está implementado; "
        f"se implementará en {phases[command]}.",
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
    sub.add_parser("doctor", help="Detecta y muestra el entorno del sistema (Fase 2).")
    sub.add_parser("config", help="Muestra la configuración efectiva (Fase 2).")
    sub.add_parser("version", help="Muestra la versión de OpenBuds Manager.")
    sub.add_parser("devices", help="Lista dispositivos Bluetooth (Fase 3).")
    sub.add_parser("codec", help="Muestra el códec activo (Fase 3/4).")
    sub.add_parser("health", help="Ejecuta un Health Check (Fase 5).")
    sub.add_parser("bench", help="Ejecuta un benchmark de enlace (Fase 5).")
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
