"""Unit tests for the device watch use case."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError

from openbuds.application.watch_devices import WatchDevicesRequest, WatchDevicesUseCase
from openbuds.domain.enums import AddressType, ConnectionState, DeviceChangeKind, DeviceIcon
from openbuds.domain.models import DeviceChangeEvent, DeviceInfo


def _device() -> DeviceInfo:
    return DeviceInfo(
        object_path="/org/bluez/hci0/dev_00_11_22_33_44_55",
        address="00:11:22:33:44:55",
        name="Buds",
        alias="Buds",
        icon=DeviceIcon.UNKNOWN,
        address_type=AddressType.UNKNOWN,
        paired=True,
        connected=False,
        trusted=False,
        blocked=False,
        services_resolved=False,
        adapter_path="/org/bluez/hci0",
        connection_state=ConnectionState.DISCONNECTED,
    )


class FakeBluetoothRepo:
    """In-memory subscription registry for the use case."""

    def __init__(self) -> None:
        self.callbacks: list[Callable[[DeviceChangeEvent], None]] = []

    def subscribe_device_changes(
        self, callback: Callable[[DeviceChangeEvent], None]
    ) -> Callable[[], None]:
        self.callbacks.append(callback)
        active = True

        def unsubscribe() -> None:
            nonlocal active
            if active:
                self.callbacks.remove(callback)
                active = False

        return unsubscribe


def test_subscribe_delegates_events_and_unsubscribe_is_idempotent() -> None:
    repository = FakeBluetoothRepo()
    received: list[DeviceChangeEvent] = []
    event = DeviceChangeEvent(DeviceChangeKind.ADDED, _device(), None)

    unsubscribe = WatchDevicesUseCase(repository).subscribe(received.append)

    assert callable(unsubscribe)
    repository.callbacks[0](event)
    unsubscribe()
    unsubscribe()

    assert received == [event]
    assert repository.callbacks == []


def test_watch_request_is_frozen() -> None:
    request = WatchDevicesRequest()

    assert request.adapter_path is None
    try:
        request.adapter_path = "/org/bluez/hci0"
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("WatchDevicesRequest must be frozen")
