"""Tests de enumeraciones del dominio."""

from __future__ import annotations

from openbuds.domain.enums import (
    AddressType,
    BluetoothProfile,
    CheckSeverity,
    CodecType,
    ConnectionState,
    DeviceIcon,
    HealthStatus,
    ProfileState,
)


def test_enums_are_unique() -> None:
    """Cada enumeración no debe tener valores duplicados (decorador @unique)."""
    for enum_cls in (
        AddressType,
        BluetoothProfile,
        CheckSeverity,
        CodecType,
        ConnectionState,
        DeviceIcon,
        HealthStatus,
        ProfileState,
    ):
        values = [m.value for m in enum_cls]
        assert len(values) == len(set(values)), f"{enum_cls.__name__} tiene duplicados"


def test_codec_values_match_wireplumber_names() -> None:
    """Los valores de CodecType deben coincidir con los nombres de bluez5.codecs."""
    assert CodecType.SBC.value == "sbc"
    assert CodecType.AAC.value == "aac"
    assert CodecType.LDAC.value == "ldac"


def test_connection_states() -> None:
    assert ConnectionState.CONNECTED.value == "connected"
    assert ConnectionState.DISCONNECTED.value == "disconnected"
