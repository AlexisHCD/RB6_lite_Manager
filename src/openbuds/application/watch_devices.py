"""Use case for observing Bluetooth device changes."""

from __future__ import annotations

from dataclasses import dataclass

from openbuds.domain.interfaces import IBluetoothRepository
from openbuds.domain.interfaces.observer import DeviceChangeCallback, Unsubscribe


@dataclass(frozen=True, slots=True)
class WatchDevicesRequest:
    """Parameters for observing device changes."""

    adapter_path: str | None = None


class WatchDevicesUseCase:
    """Subscribe to read-only Bluetooth device changes."""

    def __init__(self, bluetooth_repo: IBluetoothRepository) -> None:
        self._bluetooth = bluetooth_repo

    def subscribe(self, callback: DeviceChangeCallback) -> Unsubscribe:
        """Subscribe without filtering; the presenter filters by adapter if needed."""
        return self._bluetooth.subscribe_device_changes(callback)
