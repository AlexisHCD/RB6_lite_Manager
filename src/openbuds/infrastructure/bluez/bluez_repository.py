"""Implementación de ``IBluetoothRepository`` sobre BlueZ (D-Bus / Gio).

Estado: Fase 1 — esqueleto que cumple la interfaz. Implementación en Fase 3.
"""

from __future__ import annotations

from openbuds.domain.interfaces import IBluetoothRepository
from openbuds.domain.interfaces.observer import DeviceChangeCallback
from openbuds.domain.models import AdapterInfo, BatteryLevel, DeviceInfo, RSSIReading


class BlueZRepository(IBluetoothRepository):
    """Repositorio Bluetooth basado en el cliente D-Bus de BlueZ.

    Estado: Fase 1 — sin implementación.
    """

    def list_adapters(self) -> list[AdapterInfo]:
        raise NotImplementedError("Fase 3 (Bluetooth).")

    def list_devices(self, adapter_path: str | None = None) -> list[DeviceInfo]:
        raise NotImplementedError("Fase 3 (Bluetooth).")

    def get_device(self, device_path: str) -> DeviceInfo | None:
        raise NotImplementedError("Fase 3 (Bluetooth).")

    def get_battery(self, device_path: str) -> BatteryLevel | None:
        raise NotImplementedError("Fase 3 (Bluetooth).")

    def get_rssi(self, device_path: str) -> RSSIReading | None:
        raise NotImplementedError("Fase 3 (Bluetooth).")

    def subscribe_device_changes(self, callback: DeviceChangeCallback) -> None:
        raise NotImplementedError("Fase 3 (Bluetooth).")
