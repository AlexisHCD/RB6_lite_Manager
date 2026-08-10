"""Entry point de la CLI: ``openbuds``.

Subcomandos (planificados):
  - doctor     Detecta y muestra el entorno del sistema (stack, versiones).
  - devices    Lista dispositivos Bluetooth detectados (Fase 3).
  - codec      Muestra el códec activo de un dispositivo (Fase 3/4).
  - health     Ejecuta un Health Check (Fase 5).
  - bench      Ejecuta un benchmark de enlace (Fase 5).

Estado: Fase 1 — ``doctor`` funcional (usa el detector de entorno real);
el resto se implementa en sus fases correspondientes.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable


def _cmd_doctor(args: argparse.Namespace) -> int:
    """Detecta el entorno y lo muestra. Devuelve 0 si está soportado."""
    # Import diferido para no arrastrar dependencias innecesarias en --help.
    from openbuds.core.logging_setup import setup_logging
    from openbuds.infrastructure.system.environment_detector import detect

    setup_logging("WARNING")
    info = detect()
    print(f"SO:              {info.os_id} {info.os_version}")
    print(f"Kernel:          {info.kernel_version}")
    print(f"BlueZ:           {info.bluez_version}")
    print(f"PipeWire:        {info.pipewire_version}")
    print(f"WirePlumber:     {info.wireplumber_version} ({info.wireplumber_config_style})")
    print(f"D-Bus/systemd:   {info.dbus_version}")
    print(f"Adaptador BT:    {'sí' if info.has_bluetooth_adapter else 'no detectado'}")
    print(f"Entorno soportado: {'SÍ' if info.is_supported else 'NO'}")
    return 0 if info.is_supported else 1


def build_parser() -> argparse.ArgumentParser:
    """Construye el parser de la CLI."""
    parser = argparse.ArgumentParser(
        prog="openbuds",
        description="OpenBuds Manager — administrador de auriculares Bluetooth para Linux.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_doctor = sub.add_parser("doctor", help="Detecta y muestra el entorno del sistema.")
    p_doctor.set_defaults(func=_cmd_doctor)

    # Subcomandos pendientes de implementación (esqueleto informativo).
    sub.add_parser("devices", help="Lista dispositivos Bluetooth (Fase 3).")
    sub.add_parser("codec", help="Muestra el códec activo (Fase 3/4).")
    sub.add_parser("health", help="Ejecuta un Health Check (Fase 5).")
    sub.add_parser("bench", help="Ejecuta un benchmark de enlace (Fase 5).")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada principal de la CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "func", None):
        # Subcomando no implementado todavía.
        print(
            f"El subcomando '{args.command}' aún no está implementado "
            "(ver roadmap en docs/ROADMAP.md).",
            file=sys.stderr,
        )
        return 2

    # argparse no tipa los callables de set_defaults; lo acotamos a int.
    func: Callable[[argparse.Namespace], int] = args.func
    return func(args)


if __name__ == "__main__":
    raise SystemExit(main())
