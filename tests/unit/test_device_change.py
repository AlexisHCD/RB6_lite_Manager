"""Tests del contrato de eventos de cambio de dispositivo."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import get_args

import pytest

from openbuds.domain.enums import (
    AddressType,
    ConnectionState,
    DeviceChangeKind,
    DeviceIcon,
)
from openbuds.domain.interfaces.observer import DeviceChangeCallback, Unsubscribe
from openbuds.domain.models import DeviceChangeEvent, DeviceInfo


def make_device(object_path: str = "/org/bluez/hci0/dev_AA") -> DeviceInfo:
    return DeviceInfo(
        object_path=object_path,
        address="AA:BB:CC:DD:EE:FF",
        name="Buds",
        alias="Buds",
        icon=DeviceIcon.AUDIO_HEADSET,
        address_type=AddressType.PUBLIC,
        paired=True,
        connected=True,
        trusted=False,
        blocked=False,
        services_resolved=True,
        connection_state=ConnectionState.CONNECTED,
    )


@pytest.mark.parametrize(
    ("kind", "current", "previous"),
    [
        (DeviceChangeKind.ADDED, make_device(), None),
        (DeviceChangeKind.UPDATED, make_device(), make_device()),
        (DeviceChangeKind.REMOVED, None, make_device()),
    ],
)
def test_valid_device_change_events(
    kind: DeviceChangeKind,
    current: DeviceInfo | None,
    previous: DeviceInfo | None,
) -> None:
    event = DeviceChangeEvent(kind=kind, current=current, previous=previous)

    assert event.kind is kind
    assert event.current is current
    assert event.previous is previous


@pytest.mark.parametrize(
    ("kind", "current", "previous"),
    [
        (DeviceChangeKind.ADDED, None, None),
        (DeviceChangeKind.ADDED, make_device(), make_device()),
        (DeviceChangeKind.UPDATED, make_device(), None),
        (DeviceChangeKind.UPDATED, None, make_device()),
        (DeviceChangeKind.UPDATED, make_device("/current"), make_device("/previous")),
        (DeviceChangeKind.REMOVED, make_device(), None),
        (DeviceChangeKind.REMOVED, make_device(), make_device()),
    ],
)
def test_invalid_device_change_events_raise_value_error(
    kind: DeviceChangeKind,
    current: DeviceInfo | None,
    previous: DeviceInfo | None,
) -> None:
    with pytest.raises(ValueError):
        DeviceChangeEvent(kind=kind, current=current, previous=previous)


def test_device_change_event_is_frozen_and_slotted() -> None:
    event = DeviceChangeEvent(DeviceChangeKind.ADDED, make_device(), None)

    with pytest.raises(FrozenInstanceError):
        event.kind = DeviceChangeKind.UPDATED  # type: ignore[misc]
    with pytest.raises(AttributeError):
        event.extra = None  # type: ignore[attr-defined]


def test_device_change_observer_aliases_use_event_and_unsubscribe_contract() -> None:
    callback_args = get_args(DeviceChangeCallback)
    unsubscribe_args = get_args(Unsubscribe)

    assert callback_args[0] == [DeviceChangeEvent]
    assert callback_args[1] is None
    assert unsubscribe_args[0] == []
    assert unsubscribe_args[1] is None
