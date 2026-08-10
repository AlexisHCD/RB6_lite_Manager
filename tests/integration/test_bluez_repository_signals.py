"""Prueba opt-in del ciclo real de señales del repositorio BlueZ."""

from __future__ import annotations

import os

import pytest

from openbuds.domain.enums import DeviceChangeKind
from openbuds.domain.models import DeviceChangeEvent, DeviceInfo
from openbuds.infrastructure.bluez.bluez_repository import BlueZRepository


def _assert_event_invariants(event: DeviceChangeEvent) -> None:
    """Valida el contrato de dominio sin mostrar información del dispositivo."""
    assert isinstance(event, DeviceChangeEvent)
    assert isinstance(event.kind, DeviceChangeKind)

    if event.kind is DeviceChangeKind.ADDED:
        assert isinstance(event.current, DeviceInfo)
        assert event.previous is None
    elif event.kind is DeviceChangeKind.UPDATED:
        assert isinstance(event.current, DeviceInfo)
        assert isinstance(event.previous, DeviceInfo)
        assert event.current.object_path == event.previous.object_path
    else:
        assert event.kind is DeviceChangeKind.REMOVED
        assert event.current is None
        assert isinstance(event.previous, DeviceInfo)


@pytest.mark.integration
def test_real_bluez_repository_signal_subscription_is_read_only() -> None:
    """Comprueba snapshot A/B, worker de señales y reutilización segura del bus."""
    if os.environ.get("OPENBUDS_RUN_INTEGRATION") != "1":
        pytest.skip("integración BlueZ desactivada; usa OPENBUDS_RUN_INTEGRATION=1")

    repository = BlueZRepository()
    events: list[DeviceChangeEvent] = []
    unsubscribe = repository.subscribe_device_changes(events.append)

    for event in events:
        _assert_event_invariants(event)

    unsubscribe()
    unsubscribe()

    assert isinstance(repository.list_devices(), list)
