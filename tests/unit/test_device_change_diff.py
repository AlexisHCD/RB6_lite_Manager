"""Tests RED del diff puro entre snapshots de objetos BlueZ."""

from __future__ import annotations

from copy import deepcopy

import pytest

from openbuds.core.errors import BluetoothError
from openbuds.domain.enums import DeviceChangeKind
from openbuds.domain.models import DeviceChangeEvent, DeviceInfo
from openbuds.infrastructure.bluez.dbus_protocol import ManagedObjects
from openbuds.infrastructure.bluez.device_change_diff import (
    diff_device_snapshots,
)
from openbuds.infrastructure.bluez.object_mapper import map_device

DEVICE1 = "org.bluez.Device1"
BATTERY1 = "org.bluez.Battery1"


def device_properties(**overrides: object) -> dict[str, object]:
    properties: dict[str, object] = {
        "Address": "AA:BB:CC:DD:EE:FF",
        "Adapter": "/org/bluez/hci0",
        "Name": "Buds",
        "Alias": "Buds",
        "Paired": True,
        "Connected": True,
    }
    properties.update(overrides)
    return properties


def device_snapshot(
    path: str = "/org/bluez/hci0/dev_AA",
    *,
    device: dict[str, object] | None = None,
    extra_interfaces: dict[str, dict[str, object]] | None = None,
) -> ManagedObjects:
    interfaces = {DEVICE1: device_properties(**(device or {}))}
    if extra_interfaces is not None:
        interfaces.update(extra_interfaces)
    return {path: interfaces}


def expected_device(path: str, properties: dict[str, object]) -> DeviceInfo:
    return map_device(path, properties)


def test_equal_snapshots_produce_no_events() -> None:
    snapshot = device_snapshot()

    assert diff_device_snapshots(snapshot, deepcopy(snapshot)) == ()


def test_removed_device_has_previous_and_no_current() -> None:
    previous = device_snapshot()

    events = diff_device_snapshots(previous, {})

    assert events == (
        DeviceChangeEvent(
            kind=DeviceChangeKind.REMOVED,
            previous=expected_device(
                previous_path := next(iter(previous)), previous[previous_path][DEVICE1]
            ),
            current=None,
        ),
    )


def test_added_device_has_current_and_no_previous() -> None:
    current = device_snapshot()

    events = diff_device_snapshots({}, current)

    path = next(iter(current))
    assert events == (
        DeviceChangeEvent(
            kind=DeviceChangeKind.ADDED,
            current=expected_device(path, current[path][DEVICE1]),
            previous=None,
        ),
    )


def test_observable_device_change_is_updated() -> None:
    previous = device_snapshot()
    current = device_snapshot(device={"Alias": "New alias"})
    path = next(iter(previous))

    assert diff_device_snapshots(previous, current) == (
        DeviceChangeEvent(
            kind=DeviceChangeKind.UPDATED,
            previous=expected_device(path, previous[path][DEVICE1]),
            current=expected_device(path, current[path][DEVICE1]),
        ),
    )


def test_events_are_grouped_and_paths_are_sorted() -> None:
    removed_path = "/org/bluez/hci0/dev_AA"
    added_path = "/org/bluez/hci0/dev_BB"
    updated_path = "/org/bluez/hci0/dev_CC"
    previous: ManagedObjects = {
        updated_path: {DEVICE1: device_properties(**{"Alias": "old"})},
        removed_path: {DEVICE1: device_properties()},
    }
    current: ManagedObjects = {
        updated_path: {DEVICE1: device_properties(**{"Alias": "new"})},
        added_path: {DEVICE1: device_properties()},
    }

    events = diff_device_snapshots(previous, current)

    assert [event.kind for event in events] == [
        DeviceChangeKind.REMOVED,
        DeviceChangeKind.ADDED,
        DeviceChangeKind.UPDATED,
    ]
    assert [
        event.previous.object_path if event.previous else event.current.object_path
        for event in events
    ] == [
        removed_path,
        added_path,
        updated_path,
    ]


def test_battery_interface_change_does_not_emit_event() -> None:
    path = "/org/bluez/hci0/dev_AA"
    previous = device_snapshot(
        path,
        extra_interfaces={BATTERY1: {"Percentage": 20}},
    )
    current = device_snapshot(
        path,
        extra_interfaces={BATTERY1: {"Percentage": 80}},
    )

    assert diff_device_snapshots(previous, current) == ()


@pytest.mark.parametrize("property_name", ["RSSI", "TxPower"])
def test_rssi_and_tx_power_changes_do_not_emit_event(property_name: str) -> None:
    previous = device_snapshot(device={property_name: -50})
    current = device_snapshot(device={property_name: -20})

    assert diff_device_snapshots(previous, current) == ()


def test_irrelevant_device_property_change_does_not_emit_event() -> None:
    previous = device_snapshot(device={"Class": 1})
    current = device_snapshot(device={"Class": 2})

    assert diff_device_snapshots(previous, current) == ()


def test_device_removal_is_detected_when_path_keeps_another_interface() -> None:
    previous = device_snapshot()
    current = device_snapshot(
        extra_interfaces={BATTERY1: {"Percentage": 80}},
    )
    del current[next(iter(current))][DEVICE1]

    events = diff_device_snapshots(previous, current)

    assert events[0].kind is DeviceChangeKind.REMOVED
    assert events[0].current is None
    assert events[0].previous == expected_device(
        next(iter(previous)), previous[next(iter(previous))][DEVICE1]
    )


def test_device_addition_is_detected_on_existing_path() -> None:
    path = "/org/bluez/hci0/dev_AA"
    previous = device_snapshot(path, extra_interfaces={BATTERY1: {"Percentage": 20}})
    current = device_snapshot(path, extra_interfaces={BATTERY1: {"Percentage": 80}})

    del previous[path][DEVICE1]
    events = diff_device_snapshots(previous, current)

    assert events == (
        DeviceChangeEvent(
            kind=DeviceChangeKind.ADDED,
            current=expected_device(path, current[path][DEVICE1]),
            previous=None,
        ),
    )


@pytest.mark.parametrize(
    "invalid_properties",
    [
        {"Address": "AA"},
        {"Adapter": "/org/bluez/hci0", "Connected": 1},
    ],
)
def test_invalid_device_properties_propagate_mapper_error(
    invalid_properties: dict[str, object],
) -> None:
    previous = device_snapshot()
    path = next(iter(previous))
    current: ManagedObjects = {path: {DEVICE1: invalid_properties}}

    with pytest.raises(BluetoothError):
        diff_device_snapshots(previous, current)


def test_invalid_snapshot_does_not_return_partial_events() -> None:
    previous: ManagedObjects = {
        "/org/bluez/hci0/dev_AA": {DEVICE1: device_properties()},
    }
    current: ManagedObjects = {
        "/org/bluez/hci0/dev_AA": {DEVICE1: device_properties()},
        "/org/bluez/hci0/dev_BB": {DEVICE1: {"Address": "BB"}},
    }

    with pytest.raises(BluetoothError):
        diff_device_snapshots(previous, current)


def test_snapshots_are_not_mutated() -> None:
    previous = device_snapshot(extra_interfaces={BATTERY1: {"Percentage": 20}})
    current = device_snapshot(extra_interfaces={BATTERY1: {"Percentage": 80}})
    previous_before = deepcopy(previous)
    current_before = deepcopy(current)

    diff_device_snapshots(previous, current)

    assert previous == previous_before
    assert current == current_before
