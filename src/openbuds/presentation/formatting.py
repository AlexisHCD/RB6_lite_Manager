"""Privacy-safe formatting shared by the CLI and Qt presentation layers."""

from __future__ import annotations

import re

from openbuds.application.get_device_info import DeviceAggregate
from openbuds.domain.models import DeviceInfo

NO_DATA = "No disponible"
_REDACT_OBJECT_PATH = re.compile(r"/org/bluez/[^\s]+")
REDACT_ADDRESS = re.compile(
    r"(?<![A-Za-z0-9])[0-9A-Fa-f]{2}(?:[:_. ]?[0-9A-Fa-f]{2}){5}(?![A-Za-z0-9])"
)


def sanitize_display_field(value: str) -> str:
    """Redact addresses and object paths from a display field."""
    sanitized = _REDACT_OBJECT_PATH.sub("<redacted>", value)
    sanitized = REDACT_ADDRESS.sub("<redacted>", sanitized)
    return "".join(character if character.isprintable() else "?" for character in sanitized)[:80]


def device_display_name(device: DeviceInfo) -> str:
    """Return the preferred privacy-safe display name for a device."""
    return sanitize_display_field(device.alias or device.name or "Dispositivo sin nombre")


def connection_label(device: DeviceInfo) -> str:
    """Return the user-facing connection state label for a device."""
    if device.connected:
        return "conectado"
    if device.paired:
        return "emparejado"
    return "desconectado"


def aggregate_fields(aggregate: DeviceAggregate) -> dict[str, str]:
    """Return the aggregate fields in the order used by the CLI and GUI."""
    battery = (
        f"{aggregate.battery.percentage}%"
        if aggregate.battery is not None and aggregate.battery.percentage is not None
        else NO_DATA
    )
    rssi = (
        f"{aggregate.rssi.rssi_dbm} dBm"
        if aggregate.rssi is not None and aggregate.rssi.rssi_dbm is not None
        else NO_DATA
    )

    profile = NO_DATA
    codec = NO_DATA
    if aggregate.codec is not None and aggregate.codec.verified:
        profile = aggregate.codec.profile.value
        codec = f"{aggregate.codec.codec.value} ({aggregate.codec.profile.value})"

    sink = next(
        (
            sanitize_display_field(node.node_name)
            for node in aggregate.audio_nodes
            if node.media_class == "Audio/Sink"
        ),
        NO_DATA,
    )
    source = next(
        (
            sanitize_display_field(node.node_name)
            for node in aggregate.audio_nodes
            if node.media_class == "Audio/Source"
        ),
        NO_DATA,
    )
    return {
        "Dispositivo": device_display_name(aggregate.device),
        "Estado": connection_label(aggregate.device),
        "Batería": battery,
        "RSSI": rssi,
        "Perfil": profile,
        "Códec": codec,
        "Sink": sink,
        "Source": source,
    }


def format_aggregate(aggregate: DeviceAggregate) -> str:
    """Format an aggregate without exposing addresses or object paths."""
    return "\n".join(f"{key}: {value}" for key, value in aggregate_fields(aggregate).items())
