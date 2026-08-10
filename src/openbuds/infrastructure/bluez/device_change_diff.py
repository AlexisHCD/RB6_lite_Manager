"""Diff puro de dispositivos ``org.bluez.Device1`` entre snapshots."""

from __future__ import annotations

from openbuds.domain.enums import DeviceChangeKind
from openbuds.domain.models import DeviceChangeEvent, DeviceInfo
from openbuds.infrastructure.bluez.dbus_protocol import ManagedObjects
from openbuds.infrastructure.bluez.object_mapper import map_device

# Interfaz BlueZ considerada por este diff; las demás interfaces son auxiliares.
IFACE_DEVICE1 = "org.bluez.Device1"


def _map_devices(snapshot: ManagedObjects) -> dict[str, DeviceInfo]:
    """Mapea todos los objetos ``Device1`` de un snapshot."""
    return {
        object_path: map_device(object_path, interfaces[IFACE_DEVICE1])
        for object_path, interfaces in snapshot.items()
        if IFACE_DEVICE1 in interfaces
    }


def diff_device_snapshots(
    previous: ManagedObjects, current: ManagedObjects
) -> tuple[DeviceChangeEvent, ...]:
    """Devuelve los cambios de ``Device1`` entre dos snapshots completos.

    Cada snapshot se mapea por completo antes de construir eventos, por lo que
    un error del mapper siempre se propaga sin devolver resultados parciales.
    """
    previous_devices = _map_devices(previous)
    current_devices = _map_devices(current)

    removed = tuple(
        DeviceChangeEvent(
            kind=DeviceChangeKind.REMOVED,
            previous=previous_devices[object_path],
            current=None,
        )
        for object_path in sorted(previous_devices.keys() - current_devices.keys())
    )
    added = tuple(
        DeviceChangeEvent(
            kind=DeviceChangeKind.ADDED,
            current=current_devices[object_path],
            previous=None,
        )
        for object_path in sorted(current_devices.keys() - previous_devices.keys())
    )
    updated = tuple(
        DeviceChangeEvent(
            kind=DeviceChangeKind.UPDATED,
            previous=previous_devices[object_path],
            current=current_devices[object_path],
        )
        for object_path in sorted(previous_devices.keys() & current_devices.keys())
        if previous_devices[object_path] != current_devices[object_path]
    )
    return removed + added + updated
