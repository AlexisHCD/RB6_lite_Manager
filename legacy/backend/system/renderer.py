"""
Renderizado de reportes del sistema para terminal.

Genera una salida legible y colorida usando rich.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from backend.system.detector import SystemReport


def render_system_report(report: SystemReport, console: Console | None = None) -> None:
    """
    Imprime un reporte del sistema formateado en la consola.

    Args:
        report: Reporte del sistema a mostrar.
        console: Consola de rich. Si es None, crea una nueva.
    """
    if console is None:
        console = Console()

    _render_header(report, console)
    console.print()
    _render_distro(report, console)
    console.print()
    _render_kernel(report, console)
    console.print()
    _render_components(report, console)
    console.print()
    _render_services(report, console)
    console.print()
    _render_bluetooth(report, console)
    console.print()
    _render_codecs(report, console)


def _render_header(report: SystemReport, console: Console) -> None:
    title = Text("OpenBuds Manager — Diagnóstico del Sistema", style="bold cyan")
    console.print(Panel(title, border_style="cyan"))


def _render_distro(report: SystemReport, console: Console) -> None:
    table = Table(title="Distribución", show_header=True, header_style="bold blue")
    table.add_column("Campo", style="dim")
    table.add_column("Valor")
    table.add_row("Nombre", report.distro.name)
    table.add_row("Versión", report.distro.version)
    table.add_row("ID", report.distro.id)
    table.add_row("ID Like", " ".join(report.distro.id_like) or "—")
    console.print(table)


def _render_kernel(report: SystemReport, console: Console) -> None:
    table = Table(title="Kernel", show_header=True, header_style="bold blue")
    table.add_column("Campo", style="dim")
    table.add_column("Valor")
    table.add_row("Release", report.kernel.release)
    table.add_row("Machine", report.kernel.machine)
    table.add_row("Python", report.python_version)
    console.print(table)


def _render_components(report: SystemReport, console: Console) -> None:
    table = Table(title="Componentes del Stack", show_header=True, header_style="bold blue")
    table.add_column("Componente", style="dim")
    table.add_column("Instalado", justify="center")
    table.add_column("Versión")
    table.add_column("Ruta")

    for component in (report.bluez, report.pipewire, report.wireplumber):
        installed_text = Text("[OK]" if component.installed else "[FALTA]", style="green" if component.installed else "red")
        table.add_row(
            component.name,
            installed_text,
            component.version or "—",
            component.executable or "—",
        )

    console.print(table)


def _render_services(report: SystemReport, console: Console) -> None:
    table = Table(title="Servicios del Sistema", show_header=True, header_style="bold blue")
    table.add_column("Servicio", style="dim")
    table.add_column("Activo", justify="center")
    table.add_column("Habilitado", justify="center")
    table.add_column("Estado")

    for service in (report.bluetooth_service, report.pipewire_service, report.wireplumber_service):
        active_text = Text("SI" if service.active else "NO", style="green" if service.active else "red")
        enabled_text = Text("SI" if service.enabled else "NO", style="green" if service.enabled else "yellow")
        table.add_row(service.name, active_text, enabled_text, service.status)

    console.print(table)


def _render_bluetooth(report: SystemReport, console: Console) -> None:
    table = Table(title="Adaptadores Bluetooth", show_header=True, header_style="bold blue")
    table.add_column("Interfaz", style="dim")
    table.add_column("Estado")

    if report.bluetooth_adapters:
        for adapter in report.bluetooth_adapters:
            table.add_row(adapter, "Detectado")
    else:
        table.add_row("—", "Sin adaptadores detectados", style="red")

    console.print(table)


def _render_codecs(report: SystemReport, console: Console) -> None:
    table = Table(title="Códecs Disponibles", show_header=True, header_style="bold blue")
    table.add_column("Códec", style="dim")

    if report.codecs:
        for codec in report.codecs:
            table.add_row(codec)
    else:
        table.add_row("—", style="red")

    console.print(table)
