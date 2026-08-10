"""API pública de gestión Bluetooth."""

from __future__ import annotations

import shutil

from .manager import AdapterInfo, BluetoothError, BluetoothManager, DeviceInfo


def detect_bluez() -> bool:
    """Indica si el cliente de BlueZ está instalado en el sistema."""
    return shutil.which("bluetoothctl") is not None


__all__ = ["AdapterInfo", "BluetoothError", "BluetoothManager", "DeviceInfo", "detect_bluez"]
