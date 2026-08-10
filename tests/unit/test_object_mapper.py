"""Tests unitarios del mapper puro de objetos BlueZ."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from openbuds.core.errors import BluetoothError
from openbuds.domain.enums import AddressType, ConnectionState, DeviceIcon
from openbuds.infrastructure.bluez.object_mapper import (
    map_adapter,
    map_battery,
    map_device,
    map_rssi,
)


def test_map_adapter_maps_complete_properties() -> None:
    result = map_adapter(
        "/org/bluez/hci0",
        {
            "Address": "AA:BB:CC:DD:EE:FF",
            "Name": "hci0",
            "Alias": "Bluetooth",
            "Powered": True,
            "Discoverable": False,
            "Pairable": True,
            "Discovering": False,
            "AddressType": "public",
        },
    )

    assert result.object_path == "/org/bluez/hci0"
    assert result.address == "AA:BB:CC:DD:EE:FF"
    assert result.name == "hci0"
    assert result.alias == "Bluetooth"
    assert result.powered is True
    assert result.discoverable is False
    assert result.pairable is True
    assert result.discovering is False
    assert result.address_type is AddressType.PUBLIC


def test_map_adapter_uses_defaults_for_optional_properties() -> None:
    result = map_adapter("/org/bluez/hci0", {"Address": "AA:BB:CC:DD:EE:FF"})

    assert result.name == ""
    assert result.alias == ""
    assert result.powered is False
    assert result.discoverable is False
    assert result.pairable is False
    assert result.discovering is False
    assert result.address_type is AddressType.UNKNOWN


def test_map_adapter_requires_address() -> None:
    try:
        map_adapter("/org/bluez/hci0", {})
    except BluetoothError as exc:
        assert str(exc) == "Adapter1.Address: propiedad requerida ausente"
    else:
        raise AssertionError("expected BluetoothError")


def test_map_adapter_rejects_wrong_address_type() -> None:
    try:
        map_adapter("/org/bluez/hci0", {"Address": 1})
    except BluetoothError as exc:
        assert str(exc) == "Adapter1.Address: se esperaba str, recibido int"
    else:
        raise AssertionError("expected BluetoothError")


def test_map_adapter_rejects_non_boolean_powered() -> None:
    for value in (1, "yes"):
        try:
            map_adapter("/org/bluez/hci0", {"Address": "AA", "Powered": value})
        except BluetoothError as exc:
            assert "Adapter1.Powered" in str(exc)
        else:
            raise AssertionError("expected BluetoothError")


def test_map_adapter_unknown_address_type_becomes_unknown() -> None:
    result = map_adapter("/org/bluez/hci0", {"Address": "AA", "AddressType": "banana"})

    assert result.address_type is AddressType.UNKNOWN


def test_map_adapter_rejects_non_string_address_type() -> None:
    try:
        map_adapter("/org/bluez/hci0", {"Address": "AA", "AddressType": 42})
    except BluetoothError as exc:
        assert "Adapter1.AddressType" in str(exc)
    else:
        raise AssertionError("expected BluetoothError")


def test_map_adapter_ignores_unmapped_properties() -> None:
    result = map_adapter(
        "/org/bluez/hci0",
        {"Address": "AA", "Class": 1, "UUIDs": ["uuid"], "Modalias": "x"},
    )

    assert result.address == "AA"


def test_map_device_maps_complete_properties() -> None:
    result = map_device(
        "/org/bluez/hci0/dev_AA",
        {
            "Address": "AA:BB:CC:DD:EE:FF",
            "Adapter": "/org/bluez/hci0",
            "Name": "Buds",
            "Alias": "My Buds",
            "Icon": "audio-headset",
            "AddressType": "random",
            "Paired": True,
            "Connected": True,
            "Trusted": True,
            "Blocked": False,
            "ServicesResolved": True,
            "UUIDs": ["one", "two"],
        },
    )

    assert result.object_path == "/org/bluez/hci0/dev_AA"
    assert result.address == "AA:BB:CC:DD:EE:FF"
    assert result.adapter_path == "/org/bluez/hci0"
    assert result.name == "Buds"
    assert result.alias == "My Buds"
    assert result.icon is DeviceIcon.AUDIO_HEADSET
    assert result.address_type is AddressType.RANDOM
    assert result.paired is True
    assert result.connected is True
    assert result.connection_state is ConnectionState.CONNECTED
    assert result.trusted is True
    assert result.blocked is False
    assert result.services_resolved is True
    assert result.uuids == ("one", "two")


@pytest.mark.parametrize(
    ("props", "context"),
    [({}, "Device1.Address"), ({"Address": "AA"}, "Device1.Adapter")],
)
def test_map_device_requires_identity_properties(props: dict[str, object], context: str) -> None:
    with pytest.raises(BluetoothError, match=context):
        map_device("/device", props)


def test_map_device_rejects_non_string_adapter() -> None:
    with pytest.raises(BluetoothError, match="Device1.Adapter"):
        map_device("/device", {"Address": "AA", "Adapter": 1})


def test_map_device_uses_optional_defaults() -> None:
    result = map_device("/device", {"Address": "AA", "Adapter": "/adapter"})

    assert result.name == ""
    assert result.alias == ""
    assert result.icon is DeviceIcon.UNKNOWN
    assert result.address_type is AddressType.UNKNOWN
    assert result.paired is False
    assert result.connected is False
    assert result.connection_state is ConnectionState.DISCONNECTED
    assert result.trusted is False
    assert result.blocked is False
    assert result.services_resolved is False
    assert result.uuids == ()


def test_map_device_unknown_icon_becomes_unknown() -> None:
    result = map_device("/device", {"Address": "AA", "Adapter": "/adapter", "Icon": "future-icon"})

    assert result.icon is DeviceIcon.UNKNOWN


@pytest.mark.parametrize("uuids", [["one", 2], "abcd", b"abcd"])
def test_map_device_rejects_invalid_uuid_container(uuids: object) -> None:
    with pytest.raises(BluetoothError, match="Device1.UUIDs"):
        map_device("/device", {"Address": "AA", "Adapter": "/adapter", "UUIDs": uuids})


def test_map_device_rejects_integer_for_boolean() -> None:
    for property_name in ("Connected", "Paired"):
        with pytest.raises(BluetoothError, match=f"Device1.{property_name}"):
            map_device(
                "/device",
                {"Address": "AA", "Adapter": "/adapter", property_name: 1},
            )


def test_map_device_ignores_rssi_and_other_unmapped_properties() -> None:
    result = map_device(
        "/device",
        {
            "Address": "AA",
            "Adapter": "/adapter",
            "RSSI": -50,
            "TxPower": 8,
            "Class": 1,
            "Appearance": 1,
        },
    )

    assert result.address == "AA"


def test_map_battery_maps_properties() -> None:
    result = map_battery({"Percentage": 80, "Source": "GATT Battery Service"})

    assert result.percentage == 80
    assert result.source == "GATT Battery Service"


def test_map_battery_uses_defaults() -> None:
    result = map_battery({})

    assert result.percentage is None
    assert result.source == ""


@pytest.mark.parametrize("value", [True, "80"])
def test_map_battery_rejects_invalid_percentage_type(value: object) -> None:
    with pytest.raises(BluetoothError, match="Battery1.Percentage"):
        map_battery({"Percentage": value})


@pytest.mark.parametrize("value", [-1, 101])
def test_map_battery_wraps_percentage_invariant(value: int) -> None:
    with pytest.raises(BluetoothError) as error:
        map_battery({"Percentage": value})

    assert isinstance(error.value.__cause__, ValueError)
    assert "Battery1.Percentage fuera de rango [0, 100]" in str(error.value)


def test_map_battery_rejects_invalid_source_type() -> None:
    with pytest.raises(BluetoothError, match="Battery1.Source"):
        map_battery({"Source": 5})


def test_map_rssi_maps_values_and_preserves_utc_timestamp() -> None:
    timestamp = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)

    result = map_rssi({"RSSI": -67, "TxPower": 8}, timestamp=timestamp)

    assert result.rssi_dbm == -67
    assert result.tx_power_dbm == 8
    assert result.timestamp is timestamp


def test_map_rssi_uses_utc_now_when_timestamp_is_missing() -> None:
    before = datetime.now(UTC)
    result = map_rssi({})
    after = datetime.now(UTC)

    assert result.rssi_dbm is None
    assert result.tx_power_dbm is None
    assert result.timestamp.tzinfo is not None
    assert result.timestamp.utcoffset() == timedelta(0)
    assert before <= result.timestamp <= after


@pytest.mark.parametrize(
    ("property_name", "value"),
    [("RSSI", True), ("RSSI", "x"), ("TxPower", True)],
)
def test_map_rssi_rejects_invalid_integer_types(property_name: str, value: object) -> None:
    with pytest.raises(BluetoothError, match=f"Device1.{property_name}"):
        map_rssi({property_name: value})


def test_map_rssi_wraps_positive_rssi_invariant() -> None:
    with pytest.raises(BluetoothError) as error:
        map_rssi({"RSSI": 10})

    assert isinstance(error.value.__cause__, ValueError)


def test_map_rssi_allows_missing_rssi_when_tx_power_is_present() -> None:
    result = map_rssi({"TxPower": 8})

    assert result.rssi_dbm is None
    assert result.tx_power_dbm == 8


@pytest.mark.parametrize(
    "timestamp",
    [
        "now",
        datetime(2026, 8, 9, 12, 0),
        datetime(2026, 8, 9, 12, 0, tzinfo=timezone(timedelta(hours=2))),
    ],
)
def test_map_rssi_rejects_invalid_timestamp(timestamp: object) -> None:
    with pytest.raises(BluetoothError, match="timestamp"):
        map_rssi({}, timestamp=timestamp)  # type: ignore[arg-type]


def test_map_rssi_preserves_compliant_utc_timestamp_instance() -> None:
    timestamp = datetime(2026, 8, 9, 12, 0, tzinfo=timezone(timedelta(0)))

    result = map_rssi({}, timestamp=timestamp)

    assert result.timestamp is timestamp
