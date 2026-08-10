"""Repositorio de consultas snapshot de BlueZ."""

from __future__ import annotations

from typing import Protocol

from openbuds.domain.interfaces import IBluetoothRepository
from openbuds.domain.interfaces.observer import DeviceChangeCallback
from openbuds.domain.models import AdapterInfo, BatteryLevel, DeviceInfo, RSSIReading
from openbuds.infrastructure.bluez.dbus_client import (
    IFACE_ADAPTER1,
    IFACE_BATTERY1,
    IFACE_DEVICE1,
    BlueZDBusClient,
)
from openbuds.infrastructure.bluez.dbus_protocol import ManagedObjects
from openbuds.infrastructure.bluez.object_mapper import (
    map_adapter,
    map_battery,
    map_device,
    map_rssi,
)


class SnapshotClient(Protocol):
    """Cliente estructural capaz de obtener un snapshot de BlueZ."""

    def snapshot(self) -> ManagedObjects:
        """Devuelve el árbol actual de objetos administrados."""
        ...


class BlueZRepository(IBluetoothRepository):
    """Repositorio de solo lectura basado en snapshots frescos de BlueZ."""

    def __init__(self, client: SnapshotClient | None = None) -> None:
        self._client = client if client is not None else BlueZDBusClient()

    def list_adapters(self) -> list[AdapterInfo]:
        snapshot = self._client.snapshot()
        return [
            map_adapter(object_path, interfaces[IFACE_ADAPTER1])
            for object_path, interfaces in sorted(snapshot.items())
            if IFACE_ADAPTER1 in interfaces
        ]

    def list_devices(self, adapter_path: str | None = None) -> list[DeviceInfo]:
        snapshot = self._client.snapshot()
        devices = [
            (object_path, interfaces[IFACE_DEVICE1])
            for object_path, interfaces in sorted(snapshot.items())
            if IFACE_DEVICE1 in interfaces
        ]
        mapped = [map_device(object_path, props) for object_path, props in devices]
        if adapter_path is None:
            return mapped
        return [device for device in mapped if device.adapter_path == adapter_path]

    def get_device(self, device_path: str) -> DeviceInfo | None:
        snapshot = self._client.snapshot()
        interfaces = snapshot.get(device_path)
        if interfaces is None or IFACE_DEVICE1 not in interfaces:
            return None
        return map_device(device_path, interfaces[IFACE_DEVICE1])

    def get_battery(self, device_path: str) -> BatteryLevel | None:
        snapshot = self._client.snapshot()
        exact = snapshot.get(device_path)
        if exact is not None and IFACE_BATTERY1 in exact:
            return map_battery(exact[IFACE_BATTERY1])
        prefix = f"{device_path}/"
        for object_path, interfaces in sorted(snapshot.items()):
            if object_path.startswith(prefix) and IFACE_BATTERY1 in interfaces:
                return map_battery(interfaces[IFACE_BATTERY1])
        return None

    def get_rssi(self, device_path: str) -> RSSIReading | None:
        snapshot = self._client.snapshot()
        interfaces = snapshot.get(device_path)
        if interfaces is None or IFACE_DEVICE1 not in interfaces:
            return None
        props = interfaces[IFACE_DEVICE1]
        if "RSSI" not in props and "TxPower" not in props:
            return None
        return map_rssi(props)

    def subscribe_device_changes(self, callback: DeviceChangeCallback) -> None:
        raise NotImplementedError("subscribe_device_changes se implementará en el Incremento 2.")
