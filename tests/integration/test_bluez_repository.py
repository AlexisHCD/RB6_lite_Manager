"""Pruebas opt-in de consultas reales y solo lectura del repositorio BlueZ."""

from __future__ import annotations

import os

import pytest

from openbuds.infrastructure.bluez.bluez_repository import BlueZRepository


@pytest.mark.integration
def test_real_bluez_repository_queries_are_read_only() -> None:
    if os.environ.get("OPENBUDS_RUN_INTEGRATION") != "1":
        pytest.skip("integración BlueZ desactivada; usa OPENBUDS_RUN_INTEGRATION=1")

    repository = BlueZRepository()
    adapters = repository.list_adapters()
    assert adapters
    assert adapters == sorted(adapters, key=lambda adapter: adapter.object_path)
    assert all(adapter.address for adapter in adapters)

    devices = repository.list_devices()
    for device in devices:
        assert device.address
        assert device.adapter_path
        assert repository.get_device(device.object_path) is not None
        battery = repository.get_battery(device.object_path)
        if battery is not None and battery.percentage is not None:
            assert 0 <= battery.percentage <= 100
        repository.get_rssi(device.object_path)

    for adapter in adapters:
        assert all(
            device.adapter_path == adapter.object_path
            for device in repository.list_devices(adapter.object_path)
        )
