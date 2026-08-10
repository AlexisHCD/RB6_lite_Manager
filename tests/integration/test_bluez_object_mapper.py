"""Integración de solo lectura entre snapshots BlueZ y el mapper."""

from __future__ import annotations

import os

import pytest

from openbuds.infrastructure.bluez.dbus_client import (
    IFACE_ADAPTER1,
    IFACE_BATTERY1,
    IFACE_DEVICE1,
    BlueZDBusClient,
)
from openbuds.infrastructure.bluez.object_mapper import (
    map_adapter,
    map_battery,
    map_device,
    map_rssi,
)


@pytest.mark.integration
def test_real_bluez_objects_are_mapped_from_read_only_snapshot() -> None:
    if os.environ.get("OPENBUDS_RUN_INTEGRATION") != "1":
        pytest.skip("integración BlueZ desactivada; usa OPENBUDS_RUN_INTEGRATION=1")

    snapshot = BlueZDBusClient().snapshot()
    adapter_count = 0

    for object_path, interfaces in snapshot.items():
        adapter_props = interfaces.get(IFACE_ADAPTER1)
        if adapter_props is not None:
            adapter = map_adapter(object_path, adapter_props)
            assert adapter.address
            adapter_count += 1

        device_props = interfaces.get(IFACE_DEVICE1)
        if device_props is not None:
            device = map_device(object_path, device_props)
            assert device.address
            assert device.adapter_path
            assert isinstance(device.uuids, tuple)
            assert (device.connected and device.connection_state.value == "connected") or (
                not device.connected and device.connection_state.value == "disconnected"
            )
            if "RSSI" in device_props or "TxPower" in device_props:
                map_rssi(device_props)

        battery_props = interfaces.get(IFACE_BATTERY1)
        if battery_props is not None:
            map_battery(battery_props)

    assert adapter_count > 0
