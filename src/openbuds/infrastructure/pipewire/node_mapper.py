"""Pure mapping helpers for Bluetooth PipeWire node properties."""

from __future__ import annotations

import re

from openbuds.domain.models import BluetoothAudioNode

_BLUETOOTH_NAME = re.compile(
    r"^bluez_(?:output|input|card)[._]"
    r"([0-9a-f]{2}(?:[:_. ]?[0-9a-f]{2}){5})(?:[._].*)?$",
    re.IGNORECASE,
)
_ADDRESS_PART = re.compile(r"(?:[0-9a-f]{2}[:_. ]?){6}", re.IGNORECASE)


def normalize_address(address: str) -> str:
    """Normalize a Bluetooth address for private comparisons."""
    match = _ADDRESS_PART.search(address)
    if match:
        return "".join(character.lower() for character in match.group(0) if character.isalnum())
    return re.sub(r"[:_\s]", "", address).lower()


def to_domain_node(flat: dict[str, str]) -> BluetoothAudioNode:
    """Map one flat PipeWire property dictionary to the domain model."""
    return BluetoothAudioNode(
        node_name=flat.get("node.name", ""),
        media_class=flat.get("media.class", ""),
        profile=flat.get("api.bluez5.profile"),
        codec=flat.get("api.bluez5.codec"),
        transport=flat.get("api.bluez5.transport"),
    )


def _name_address(value: str) -> str | None:
    match = _BLUETOOTH_NAME.fullmatch(value)
    return normalize_address(match.group(1)) if match else None


def match_nodes_by_address(
    address: str, flat_nodes: list[dict[str, str]]
) -> list[BluetoothAudioNode]:
    """Match nodes by address, preferring exact property, node, then device names."""
    normalized = normalize_address(address)
    property_matches = [
        node
        for node in flat_nodes
        if normalize_address(node.get("api.bluez5.address", "")) == normalized
    ]
    if property_matches:
        return [to_domain_node(node) for node in property_matches]

    node_matches = [
        node for node in flat_nodes if _name_address(node.get("node.name", "")) == normalized
    ]
    if node_matches:
        return [to_domain_node(node) for node in node_matches]

    device_matches = [
        node for node in flat_nodes if _name_address(node.get("device.name", "")) == normalized
    ]
    return [to_domain_node(node) for node in device_matches]
