"""Pruebas unitarias del gestor Bluetooth sin DBus real."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from backend.bluetooth import BluetoothError, BluetoothManager

if TYPE_CHECKING:
    from dbus_next import Variant


class FakeProperties:
    def __init__(self, interfaces: dict[str, dict[str, Any]]) -> None:
        self.interfaces = interfaces
        self.set_calls: list[tuple[str, str, Variant]] = []

    async def call_set(self, interface: str, name: str, value: Variant) -> None:
        self.set_calls.append((interface, name, value))
        self.interfaces[interface][name] = value


class FakeInterface:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __getattr__(self, name: str) -> Any:
        async def method(*_args: Any) -> None:
            self.calls.append(name)
        return method


class FakeProxy:
    def __init__(self, interfaces: dict[str, dict[str, Any]]) -> None:
        self.properties = FakeProperties(interfaces)
        self.methods = FakeInterface()

    def get_interface(self, name: str) -> Any:
        if name == "org.freedesktop.DBus.Properties":
            return self.properties
        if name == "org.freedesktop.DBus.ObjectManager":
            return self
        return self.methods

    async def call_get_managed_objects(self) -> dict[str, Any]:
        return {}


class FakeBus:
    def __init__(self) -> None:
        self.objects = {
            "/org/bluez/hci0": {"org.bluez.Adapter1": {
                "Address": "AA:BB:CC:DD:EE:FF", "Name": "hci0", "Alias": "Bluetooth",
                "Powered": True, "Discoverable": False, "Pairable": True, "Discovering": False,
            }},
            "/org/bluez/hci0/dev_00": {"org.bluez.Device1": {
                "Name": "Redmi Buds 6 Lite", "Address": "00:11:22:33:44:55", "RSSI": -42,
                "Connected": True, "Paired": True, "Trusted": False, "Icon": "audio-card",
            }, "org.bluez.Battery1": {"Percentage": 85}},
        }

    async def connect(self) -> None:
        return None

    def disconnect(self) -> None:
        return None

    async def introspect(self, _service: str, _path: str) -> object:
        return object()

    def get_proxy_object(self, _service: str, path: str, _introspection: object) -> Any:
        proxy = FakeProxy({})
        if path == "/":
            proxy.call_get_managed_objects = self._objects  # type: ignore[method-assign]
        return proxy

    async def _objects(self) -> dict[str, Any]:
        return self.objects


def test_manager_lists_adapters_and_devices() -> None:
    manager = BluetoothManager(bus_factory=FakeBus)
    try:
        adapters = manager.adapters()
        devices = manager.devices()
        assert adapters[0].powered
        assert devices[0].battery == 85
        assert devices[0].rssi == -42
    finally:
        manager.close()


def test_manager_calls_device_operations() -> None:
    manager = BluetoothManager(bus_factory=FakeBus)
    try:
        manager.connect("/org/bluez/hci0/dev_00")
        manager.disconnect("/org/bluez/hci0/dev_00")
    finally:
        manager.close()


def test_manager_raises_when_bus_is_unavailable() -> None:
    def unavailable() -> Any:
        raise OSError("sin bus")

    with pytest.raises(BluetoothError, match="BlueZ/DBus"):
        BluetoothManager(bus_factory=unavailable)
