from __future__ import annotations

import pytest

from openbuds.core.errors import BluetoothError
from openbuds.infrastructure.bluez.dbus_client import BlueZDBusClient
from openbuds.infrastructure.bluez.dbus_protocol import (
    DBUS_CALL_TIMEOUT_MS,
    GioDBusProtocol,
    ManagedObjects,
)

SNAPSHOT: ManagedObjects = {
    "/org/bluez/hci0": {
        "org.bluez.Adapter1": {"Address": "AA:BB:CC:DD:EE:FF"},
    }
}


class FakeGLibError(Exception):
    pass


class FakeGLib:
    Error = FakeGLibError


class FakeReply:
    def __init__(self, value: object, signature: str = "(a{oa{sa{sv}}})") -> None:
        self.value = value
        self.signature = signature

    def get_type_string(self) -> str:
        return self.signature

    def unpack(self) -> object:
        return self.value


class FakeProxy:
    def __init__(self, reply: FakeReply | None = None, error: Exception | None = None) -> None:
        self.reply = reply
        self.error = error
        self.calls: list[tuple[object, ...]] = []

    def call_sync(self, *args: object) -> FakeReply:
        self.calls.append(args)
        if self.error is not None:
            raise self.error
        assert self.reply is not None
        return self.reply


class FakeGio:
    class BusType:
        SYSTEM = "system"

    class DBusProxyFlags:
        DO_NOT_AUTO_START = "no-auto-start-proxy"

    class DBusCallFlags:
        NO_AUTO_START = "no-auto-start-call"

    def __init__(self, proxy: FakeProxy, error: Exception | None = None) -> None:
        self.proxy = proxy
        self.error = error
        self.new_for_bus_sync_calls: list[tuple[object, ...]] = []
        self.DBusProxy = self

    def new_for_bus_sync(self, *args: object) -> FakeProxy:
        self.new_for_bus_sync_calls.append(args)
        if self.error is not None:
            raise self.error
        return self.proxy


def make_loader(gio: FakeGio):
    def loader() -> tuple[FakeGio, type[FakeGLib]]:
        return gio, FakeGLib

    return loader


def test_snapshot_uses_exact_gio_calls_and_returns_native_snapshot() -> None:
    proxy = FakeProxy(FakeReply((SNAPSHOT,)))
    gio = FakeGio(proxy)

    protocol = GioDBusProtocol(loader=make_loader(gio))

    assert protocol.get_managed_objects() == SNAPSHOT
    assert gio.new_for_bus_sync_calls == [
        (
            gio.BusType.SYSTEM,
            gio.DBusProxyFlags.DO_NOT_AUTO_START,
            None,
            "org.bluez",
            "/",
            "org.freedesktop.DBus.ObjectManager",
            None,
        )
    ]
    assert proxy.calls == [
        (
            "GetManagedObjects",
            None,
            gio.DBusCallFlags.NO_AUTO_START,
            DBUS_CALL_TIMEOUT_MS,
            None,
        )
    ]


@pytest.mark.parametrize(
    "reply",
    [
        FakeReply((SNAPSHOT,), "a{oa{sa{sv}}}"),
        FakeReply(SNAPSHOT),
        FakeReply((SNAPSHOT, SNAPSHOT)),
        FakeReply(([],)),
        FakeReply(({1: {}},)),
        FakeReply(({"/path": {1: {}}},)),
        FakeReply(({"/path": {"iface": []}},)),
        FakeReply(({"/path": {"iface": {1: True}}},)),
    ],
)
def test_snapshot_rejects_invalid_signature_or_shape(reply: FakeReply) -> None:
    gio = FakeGio(FakeProxy(reply))

    with pytest.raises(BluetoothError):
        GioDBusProtocol(loader=make_loader(gio)).get_managed_objects()


def test_glib_error_building_proxy_is_wrapped_with_cause() -> None:
    cause = FakeGLibError("system bus unavailable")
    gio = FakeGio(FakeProxy(FakeReply((SNAPSHOT,))), error=cause)

    with pytest.raises(BluetoothError, match="construir el proxy") as raised:
        GioDBusProtocol(loader=make_loader(gio))

    assert raised.value.__cause__ is cause


def test_glib_error_calling_snapshot_is_wrapped_with_cause() -> None:
    cause = FakeGLibError("BlueZ unavailable")
    gio = FakeGio(FakeProxy(FakeReply((SNAPSHOT,)), error=cause))
    protocol = GioDBusProtocol(loader=make_loader(gio))

    with pytest.raises(BluetoothError, match="obtener el snapshot") as raised:
        protocol.get_managed_objects()

    assert raised.value.__cause__ is cause


@pytest.mark.parametrize("loader_error", [ImportError("gi missing"), ValueError("Gio version")])
def test_gi_loader_errors_are_actionable(loader_error: Exception) -> None:
    def loader() -> tuple[FakeGio, type[FakeGLib]]:
        raise loader_error

    with pytest.raises(BluetoothError, match="make check-runtime") as raised:
        GioDBusProtocol(loader=loader)

    assert raised.value.__cause__ is loader_error


class FakeProvider:
    def __init__(self, snapshot: ManagedObjects) -> None:
        self.snapshot_value = snapshot
        self.calls = 0

    def get_managed_objects(self) -> ManagedObjects:
        self.calls += 1
        return self.snapshot_value


def test_client_delegates_snapshot_to_injected_provider() -> None:
    provider = FakeProvider(SNAPSHOT)
    client = BlueZDBusClient(provider=provider)

    assert client.snapshot() == SNAPSHOT
    assert provider.calls == 1


def test_client_accepts_falsy_injected_provider() -> None:
    class FalsyProvider(FakeProvider):
        def __bool__(self) -> bool:
            return False

    provider = FalsyProvider(SNAPSHOT)
    client = BlueZDBusClient(provider=provider)

    assert client.snapshot() == SNAPSHOT
    assert provider.calls == 1
