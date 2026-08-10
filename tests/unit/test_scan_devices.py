"""Pruebas del caso de uso de listado de dispositivos."""

from __future__ import annotations

from dataclasses import replace

import pytest

from openbuds.application.scan_devices import ScanDevicesRequest, ScanDevicesUseCase
from openbuds.core.errors import BluetoothError
from openbuds.domain.enums import AddressType, DeviceIcon
from openbuds.domain.models import DeviceInfo


def _device(name: str, paired: bool) -> DeviceInfo:
    return DeviceInfo(
        object_path=f"/org/bluez/hci0/dev_{name}",
        address="AA:BB:CC:DD:EE:FF",
        name=name,
        alias=name,
        icon=DeviceIcon.UNKNOWN,
        address_type=AddressType.UNKNOWN,
        paired=paired,
        connected=False,
        trusted=False,
        blocked=False,
        services_resolved=False,
    )


class FakeBluetoothRepository:
    def __init__(self, devices: list[DeviceInfo]) -> None:
        self.devices = devices
        self.adapter_paths: list[str | None] = []

    def list_devices(self, adapter_path: str | None = None) -> list[DeviceInfo]:
        self.adapter_paths.append(adapter_path)
        return self.devices


def test_delegates_adapter_and_preserves_repository_order() -> None:
    devices = [_device("second", False), _device("first", True)]
    repository = FakeBluetoothRepository(devices)

    result = ScanDevicesUseCase(repository).execute(
        ScanDevicesRequest(adapter_path="/org/bluez/hci1")
    )

    assert repository.adapter_paths == ["/org/bluez/hci1"]
    assert result == devices


def test_paired_only_filters_without_reordering() -> None:
    devices = [_device("a", False), _device("b", True), _device("c", True)]
    repository = FakeBluetoothRepository(devices)

    result = ScanDevicesUseCase(repository).execute(ScanDevicesRequest(include_paired_only=True))

    assert result == [devices[1], devices[2]]


def test_false_returns_all_devices() -> None:
    devices = [_device("a", False), _device("b", True)]
    repository = FakeBluetoothRepository(devices)

    assert ScanDevicesUseCase(repository).execute(ScanDevicesRequest()) == devices


def test_empty_repository_returns_empty_list() -> None:
    repository = FakeBluetoothRepository([])

    assert ScanDevicesUseCase(repository).execute(ScanDevicesRequest()) == []


def test_repository_error_is_propagated_identically() -> None:
    error = BluetoothError("snapshot failed")

    class ErrorRepository(FakeBluetoothRepository):
        def list_devices(self, adapter_path: str | None = None) -> list[DeviceInfo]:
            raise error

    caught: BluetoothError
    with pytest.raises(BluetoothError) as raised:
        ScanDevicesUseCase(ErrorRepository([])).execute(ScanDevicesRequest())
    caught = raised.value

    assert caught is error


def test_request_can_be_updated_without_mutating_original() -> None:
    request = ScanDevicesRequest(adapter_path="/org/bluez/hci0")

    paired_request = replace(request, include_paired_only=True)

    assert request.include_paired_only is False
    assert paired_request.include_paired_only is True
