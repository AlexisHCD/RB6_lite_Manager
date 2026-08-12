"""Observed Bluetooth audio node properties."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BluetoothAudioNode:
    """Observed properties of one Bluetooth audio node."""

    node_name: str
    media_class: str
    profile: str | None
    codec: str | None
    transport: str | None
