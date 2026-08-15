"""Tests for the presentation formatter shared by CLI and GUI."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from openbuds.application.get_device_info import DeviceAggregate
from openbuds.domain.enums import (
    AddressType,
    BluetoothProfile,
    CodecType,
    ConnectionState,
    DeviceIcon,
)
from openbuds.domain.models import (
    BatteryLevel,
    BluetoothAudioNode,
    CodecInfo,
    DeviceInfo,
    RSSIReading,
)
from openbuds.presentation.formatting import (
    aggregate_fields,
    connection_label,
    device_display_name,
    format_aggregate,
    sanitize_display_field,
)


def _device(*, connected: bool = True, paired: bool = True, alias: str = "Buds") -> DeviceInfo:
    return DeviceInfo(
        object_path="/org/bluez/hci0/dev_00_11_22_33_44_55",
        address="00:11:22:33:44:55",
        name="Redmi Buds",
        alias=alias,
        icon=DeviceIcon.UNKNOWN,
        address_type=AddressType.UNKNOWN,
        paired=paired,
        connected=connected,
        trusted=False,
        blocked=False,
        services_resolved=True,
        connection_state=(ConnectionState.CONNECTED if connected else ConnectionState.DISCONNECTED),
    )


def _aggregate(
    *,
    battery_available: bool = True,
    rssi_available: bool = True,
    codec: CodecInfo | None = None,
    audio_nodes: tuple[BluetoothAudioNode, ...] = (
        BluetoothAudioNode(
            "bluez_output.00:11:22:33:44:55.1", "Audio/Sink", "a2dp-sink", "sbc", None
        ),
        BluetoothAudioNode("bluez_output.second", "Audio/Sink", "a2dp-sink", "sbc", None),
        BluetoothAudioNode(
            "bluez_input.00_11_22_33_44_55.1", "Audio/Source", "headset-head-unit", "msbc", None
        ),
    ),
) -> DeviceAggregate:
    if codec is None:
        codec = CodecInfo(CodecType.SBC, BluetoothProfile.A2DP)
    return DeviceAggregate(
        device=_device(),
        battery=BatteryLevel(87) if battery_available else None,
        rssi=RSSIReading(-45, datetime.now(UTC)) if rssi_available else None,
        codec=codec,
        audio_nodes=audio_nodes,
    )


def test_aggregate_fields_and_text_match_the_cli_contract() -> None:
    aggregate = _aggregate()

    fields = aggregate_fields(aggregate)

    assert fields == {
        "Dispositivo": "Buds",
        "Estado": "conectado",
        "Batería": "87%",
        "RSSI": "-45 dBm",
        "Perfil": "a2dp",
        "Códec": "sbc (a2dp)",
        "Sink": "Disponible",
        "Source": "Disponible",
    }
    assert format_aggregate(aggregate) == "\n".join(
        f"{key}: {value}" for key, value in fields.items()
    )


def test_unverified_codec_and_missing_optional_values_are_unavailable() -> None:
    aggregate = _aggregate(
        battery_available=False,
        rssi_available=False,
        codec=CodecInfo(CodecType.UNKNOWN, BluetoothProfile.UNKNOWN, verified=False),
        audio_nodes=(),
    )

    fields = aggregate_fields(aggregate)

    assert fields["Batería"] == "No disponible"
    assert fields["RSSI"] == "No disponible"
    assert fields["Perfil"] == "No disponible"
    assert fields["Códec"] == "No disponible"
    assert fields["Sink"] == "No disponible"
    assert fields["Source"] == "No disponible"


def test_aggregate_format_never_displays_mac_or_object_path() -> None:
    output = format_aggregate(_aggregate())

    assert "00:11:22:33:44:55" not in output
    assert "/org/bluez/" not in output


def test_sanitize_display_field_redacts_hyphenated_mac_and_generic_object_paths() -> None:
    mac = "AA-BB-CC-DD-EE-FF"
    io_path = "/io/example/object"
    xyz_path = "/xyz/example/object"

    sanitized = sanitize_display_field(f"Device {mac} {io_path} {xyz_path}")

    assert sanitized == "Device <redacted> <redacted> <redacted>"
    assert mac not in sanitized
    assert io_path not in sanitized
    assert xyz_path not in sanitized


@pytest.mark.parametrize(
    ("alias", "name", "expected"),
    [("Preferred", "Name", "Preferred"), ("", "Name", "Name"), ("", "", "Dispositivo sin nombre")],
)
def test_device_display_name_uses_safe_fallbacks(alias: str, name: str, expected: str) -> None:
    assert device_display_name(replace(_device(alias=alias), name=name)) == expected


@pytest.mark.parametrize(
    ("connected", "paired", "expected"),
    [(True, True, "conectado"), (False, True, "emparejado"), (False, False, "desconectado")],
)
def test_connection_label(connected: bool, paired: bool, expected: str) -> None:
    assert connection_label(_device(connected=connected, paired=paired)) == expected
