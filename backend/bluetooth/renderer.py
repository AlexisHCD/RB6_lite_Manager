"""Renderizado Rich para información obtenida de BlueZ."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.table import Table

from ob_logging.logger import get_logger

if TYPE_CHECKING:
    from rich.console import Console

    from .manager import AdapterInfo, DeviceInfo

logger = get_logger(__name__)


def render_bluetooth_status(console: Console, adapters: tuple[AdapterInfo, ...],
                            devices: tuple[DeviceInfo, ...]) -> None:
    """Muestra adaptadores y dispositivos en tablas legibles."""
    adapter_table = Table(title="Adaptadores Bluetooth")
    for column in ("Interfaz", "Dirección", "Nombre", "Encendido", "Descubriendo"):
        adapter_table.add_column(column)
    for adapter in adapters:
        adapter_table.add_row(
            adapter.path.rsplit("/", 1)[-1], adapter.address, adapter.alias or adapter.name,
            "sí" if adapter.powered else "no", "sí" if adapter.discovering else "no",
        )
    console.print(adapter_table)

    device_table = Table(title="Dispositivos Bluetooth")
    for column in ("Nombre", "Dirección", "Conectado", "RSSI", "Batería"):
        device_table.add_column(column)
    for device in devices:
        device_table.add_row(device.name or "(sin nombre)", device.address,
                             "sí" if device.connected else "no", str(device.rssi or "-"),
                             f"{device.battery}%" if device.battery is not None else "-")
    console.print(device_table)
