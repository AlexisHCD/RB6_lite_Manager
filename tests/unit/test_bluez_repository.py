"""Tests unitarios del repositorio BlueZ basado en snapshots."""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from openbuds.core.errors import BluetoothError
from openbuds.infrastructure.bluez.bluez_repository import BlueZRepository
from openbuds.infrastructure.bluez.dbus_protocol import ManagedObjects


class FakeSnapshotClient:
    def __init__(self, snapshots: Iterable[ManagedObjects]) -> None:
        self.snapshots = iter(snapshots)
        self.calls = 0
        self.device_method_calls: list[tuple[str, str]] = []

    def __bool__(self) -> bool:
        return False

    def snapshot(self) -> ManagedObjects:
        self.calls += 1
        return next(self.snapshots)

    def call_device_method(self, device_path: str, method: str) -> None:
        self.device_method_calls.append((device_path, method))


class ErrorSnapshotClient:
    def __init__(self, error: BluetoothError) -> None:
        self.error = error
        self.calls = 0

    def snapshot(self) -> ManagedObjects:
        self.calls += 1
        raise self.error


def test_list_adapters_maps_only_adapters_in_object_path_order() -> None:
    client = FakeSnapshotClient(
        [
            {
                "/org/bluez/hci1": {
                    "org.bluez.Adapter1": {"Address": "11"},
                },
                "/org/bluez/hci0": {
                    "org.bluez.Adapter1": {"Address": "00"},
                    "org.bluez.Device1": {},
                },
                "/org/bluez/hci0/dev_AA": {
                    "org.bluez.Device1": {"Address": "AA", "Adapter": "/org/bluez/hci0"},
                },
            }
        ]
    )

    result = BlueZRepository(client).list_adapters()

    assert [adapter.object_path for adapter in result] == [
        "/org/bluez/hci0",
        "/org/bluez/hci1",
    ]
    assert [adapter.address for adapter in result] == ["00", "11"]
    assert client.calls == 1


def test_connect_and_disconnect_delegate_to_device_method() -> None:
    client = FakeSnapshotClient([{}])
    repository = BlueZRepository(client)

    repository.connect("/org/bluez/hci0/dev_00_11_22_33_44_55")
    repository.disconnect("/org/bluez/hci0/dev_00_11_22_33_44_55")

    assert client.device_method_calls == [
        ("/org/bluez/hci0/dev_00_11_22_33_44_55", "Connect"),
        ("/org/bluez/hci0/dev_00_11_22_33_44_55", "Disconnect"),
    ]


def test_connect_propagates_client_error() -> None:
    error = BluetoothError("connect failed")

    class ErrorClient(FakeSnapshotClient):
        def call_device_method(self, device_path: str, method: str) -> None:
            del device_path, method
            raise error

    with pytest.raises(BluetoothError) as raised:
        BlueZRepository(ErrorClient([{}])).connect("/org/bluez/hci0/dev_00_11_22_33_44_55")

    assert raised.value is error


def test_list_adapters_returns_empty_list_for_empty_snapshot() -> None:
    client = FakeSnapshotClient([{}])

    result = BlueZRepository(client).list_adapters()

    assert result == []
    assert client.calls == 1


def test_list_adapters_consumes_a_fresh_snapshot_on_each_call() -> None:
    client = FakeSnapshotClient(
        [
            {"/org/bluez/hci0": {"org.bluez.Adapter1": {"Address": "00"}}},
            {"/org/bluez/hci1": {"org.bluez.Adapter1": {"Address": "11"}}},
        ]
    )
    repository = BlueZRepository(client)

    first = repository.list_adapters()
    second = repository.list_adapters()

    assert [adapter.object_path for adapter in first] == ["/org/bluez/hci0"]
    assert [adapter.object_path for adapter in second] == ["/org/bluez/hci1"]
    assert client.calls == 2


def test_list_devices_filters_exact_adapter_and_sorts_paths() -> None:
    client = FakeSnapshotClient(
        [
            {
                "/org/bluez/hci01/dev_B": {
                    "org.bluez.Device1": {"Address": "B", "Adapter": "/org/bluez/hci01"},
                },
                "/org/bluez/hci0/dev_C": {
                    "org.bluez.Device1": {"Address": "C", "Adapter": "/org/bluez/hci0"},
                },
                "/org/bluez/hci0/dev_A": {
                    "org.bluez.Device1": {"Address": "A", "Adapter": "/org/bluez/hci0"},
                    "org.bluez.Battery1": {"Percentage": 50},
                },
            }
        ]
    )

    result = BlueZRepository(client).list_devices("/org/bluez/hci0")

    assert [device.object_path for device in result] == [
        "/org/bluez/hci0/dev_A",
        "/org/bluez/hci0/dev_C",
    ]
    assert client.calls == 1


def test_list_devices_without_adapter_filter_returns_all_sorted_devices() -> None:
    client = FakeSnapshotClient(
        [
            {
                "/adapter1/dev_B": {"org.bluez.Device1": {"Address": "B", "Adapter": "/adapter1"}},
                "/adapter0/dev_A": {"org.bluez.Device1": {"Address": "A", "Adapter": "/adapter0"}},
            }
        ]
    )

    result = BlueZRepository(client).list_devices()

    assert [device.object_path for device in result] == [
        "/adapter0/dev_A",
        "/adapter1/dev_B",
    ]
    assert client.calls == 1


def test_list_devices_with_unmatched_adapter_returns_empty_list() -> None:
    client = FakeSnapshotClient(
        [{"/adapter0/dev_A": {"org.bluez.Device1": {"Address": "A", "Adapter": "/adapter0"}}}]
    )

    result = BlueZRepository(client).list_devices("/adapter-missing")

    assert result == []
    assert client.calls == 1


def test_get_device_requires_exact_path_and_device_interface() -> None:
    client = FakeSnapshotClient(
        [
            {
                "/device": {
                    "org.bluez.Device1": {"Address": "AA", "Adapter": "/adapter"},
                },
                "/other": {"org.bluez.Battery1": {"Percentage": 20}},
            },
            {"/device": {"org.bluez.Battery1": {"Percentage": 20}}},
            {},
        ]
    )
    repository = BlueZRepository(client)

    device = repository.get_device("/device")
    assert device is not None
    assert device.address == "AA"
    assert repository.get_device("/device") is None
    assert repository.get_device("/missing") is None
    assert client.calls == 3


def test_get_battery_prefers_exact_path_then_sorted_children() -> None:
    client = FakeSnapshotClient(
        [
            {
                "/device": {
                    "org.bluez.Battery1": {"Percentage": 90},
                },
                "/device/battery1": {"org.bluez.Battery1": {"Percentage": 10}},
                "/device/battery0": {"org.bluez.Battery1": {"Percentage": 20}},
            },
            {
                "/device/battery1": {"org.bluez.Battery1": {"Percentage": 10}},
                "/device/battery0": {"org.bluez.Battery1": {"Percentage": 20}},
            },
            {"/device/other": {"org.bluez.Device1": {"Address": "AA", "Adapter": "/adapter"}}},
        ]
    )
    repository = BlueZRepository(client)

    exact = repository.get_battery("/device")
    child = repository.get_battery("/device")
    missing = repository.get_battery("/device")

    assert exact is not None and exact.percentage == 90
    assert child is not None and child.percentage == 20
    assert missing is None
    assert client.calls == 3


def test_get_battery_does_not_match_a_path_with_only_a_common_prefix() -> None:
    client = FakeSnapshotClient(
        [
            {
                "/device2/battery0": {"org.bluez.Battery1": {"Percentage": 20}},
            }
        ]
    )

    result = BlueZRepository(client).get_battery("/device")

    assert result is None
    assert client.calls == 1


@pytest.mark.parametrize(
    ("properties", "expected_rssi", "expected_tx_power"),
    [({"RSSI": -60}, -60, None), ({"TxPower": 8}, None, 8)],
)
def test_get_rssi_maps_available_properties(
    properties: dict[str, object], expected_rssi: int | None, expected_tx_power: int | None
) -> None:
    client = FakeSnapshotClient([{"/device": {"org.bluez.Device1": properties}}])

    result = BlueZRepository(client).get_rssi("/device")

    assert result is not None
    assert result.rssi_dbm == expected_rssi
    assert result.tx_power_dbm == expected_tx_power
    assert result.timestamp.tzinfo is not None
    offset = result.timestamp.utcoffset()
    assert offset is not None
    assert offset.total_seconds() == 0


def test_get_rssi_returns_none_without_device_or_reading_properties() -> None:
    client = FakeSnapshotClient(
        [
            {
                "/device": {"org.bluez.Device1": {"Address": "AA", "Adapter": "/adapter"}},
            },
            {"/device": {"org.bluez.Battery1": {"Percentage": 40}}},
            {},
        ]
    )
    repository = BlueZRepository(client)

    assert repository.get_rssi("/device") is None
    assert repository.get_rssi("/device") is None
    assert repository.get_rssi("/device") is None
    assert client.calls == 3


@pytest.mark.parametrize(
    "query",
    [
        lambda repository: repository.list_adapters(),
        lambda repository: repository.list_devices(),
        lambda repository: repository.get_device("/device"),
        lambda repository: repository.get_battery("/device"),
        lambda repository: repository.get_rssi("/device"),
    ],
)
def test_snapshot_bluetooth_error_is_propagated_identically(query: object) -> None:
    error = BluetoothError("snapshot failed")
    client = ErrorSnapshotClient(error)

    with pytest.raises(BluetoothError) as raised:
        query(BlueZRepository(client))  # type: ignore[operator]

    assert raised.value is error
    assert raised.value.__cause__ is error.__cause__


def test_adapter_mapper_bluetooth_error_is_propagated_without_wrapping() -> None:
    client = FakeSnapshotClient([{"/org/bluez/hci0": {"org.bluez.Adapter1": {}}}])

    with pytest.raises(BluetoothError) as raised:
        BlueZRepository(client).list_adapters()

    assert str(raised.value) == "Adapter1.Address: propiedad requerida ausente"
    assert raised.value.__cause__ is None


def test_battery_mapper_bluetooth_error_preserves_value_error_cause() -> None:
    client = FakeSnapshotClient([{"/device/battery0": {"org.bluez.Battery1": {"Percentage": 101}}}])

    with pytest.raises(BluetoothError) as raised:
        BlueZRepository(client).get_battery("/device")

    assert str(raised.value) == "Battery1.Percentage fuera de rango [0, 100]: 101"
    assert isinstance(raised.value.__cause__, ValueError)
