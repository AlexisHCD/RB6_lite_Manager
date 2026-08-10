"""
CLI de OpenBuds Manager.

Uso:
    openbuds doctor    — Diagnóstico del sistema
    openbuds config    — Mostrar configuración actual
    openbuds version   — Versión de la aplicación
"""

from __future__ import annotations

import click
from rich.console import Console

from backend.bluetooth import BluetoothError, BluetoothManager
from backend.bluetooth.renderer import render_bluetooth_status
from backend.config import ConfigManager
from backend.system.detector import SystemReport, detect_system
from backend.system.renderer import render_system_report
from ob_logging.logger import configure_logging, get_logger

logger = get_logger(__name__)
console = Console()

_APP_VERSION = "0.1.0"


@click.group()
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="Habilita logs detallados en consola.",
)
def cli(verbose: bool) -> None:
    """OpenBuds Manager — Administrador de auriculares Bluetooth para Linux."""
    configure_logging(enable_console=verbose, enable_file=True)
    logger.info("OpenBuds Manager v%s iniciado", _APP_VERSION)


@cli.command()
def doctor() -> None:
    """Ejecuta un diagnóstico completo del sistema."""
    console.print("[bold cyan]Analizando sistema...[/]")
    report = detect_system()
    render_system_report(report, console)

    issues = _check_issues(report)
    if issues:
        console.print()
        console.print("[bold yellow]Problemas detectados:[/]")
        for issue in issues:
            console.print(f"  [yellow]⚠[/] {issue}")
    else:
        console.print()
        console.print("[bold green]✓ Sistema en buen estado.[/]")


@cli.command()
def config() -> None:
    """Muestra la configuración actual."""
    cm = ConfigManager()
    cfg = cm.get()
    console.print("[bold cyan]Configuración actual:[/]")
    console.print(f"  App: {cfg.app_name} v{cfg.version}")
    console.print(f"  Logging level: {cfg.logging.level}")
    console.print(f"  Bluetooth auto-detect: {cfg.bluetooth.auto_detect_adapter}")
    console.print(f"  Preferred codecs: {', '.join(cfg.bluetooth.preferred_codecs)}")
    console.print(f"  Backup enabled: {cfg.backup.enabled}")
    console.print(f"  Config file: {cm.config_path}")


@cli.command()
def version() -> None:
    """Muestra la versión de la aplicación."""
    console.print(f"OpenBuds Manager v{_APP_VERSION}")


@cli.group()
def bluetooth() -> None:
    """Operaciones de gestión Bluetooth."""


@bluetooth.command("status")
def bluetooth_status() -> None:
    """Muestra adaptadores y dispositivos conocidos por BlueZ."""
    try:
        with BluetoothManager() as manager:
            render_bluetooth_status(console, manager.adapters(), manager.devices())
    except BluetoothError as exc:
        console.print(f"[bold yellow]BlueZ no disponible:[/] {exc}")


def _check_issues(report: SystemReport) -> list[str]:
    """Verifica si hay problemas en el reporte del sistema."""
    issues: list[str] = []

    if not report.bluez.installed:
        issues.append("BlueZ no está instalado.")
    if not report.pipewire.installed:
        issues.append("PipeWire no está instalado.")
    if not report.wireplumber.installed:
        issues.append("WirePlumber no está instalado.")
    if not report.bluetooth_service.active:
        issues.append("Servicio bluetooth.service no está activo.")
    if not report.pipewire_service.active:
        issues.append("Servicio pipewire.service no está activo.")
    if not report.wireplumber_service.active:
        issues.append("Servicio wireplumber.service no está activo.")
    if not report.bluetooth_adapters:
        issues.append("No se detectaron adaptadores Bluetooth.")

    return issues


def main() -> None:
    """Punto de entrada del CLI."""
    cli()


if __name__ == "__main__":
    main()
