"""Tests for pure PipeWire node mapping helpers."""

from __future__ import annotations

import pytest

from openbuds.infrastructure.pipewire.node_mapper import (
    match_nodes_by_address,
    normalize_address,
    to_domain_node,
)

ADDRESS = "00:11:22:33:44:55"


@pytest.mark.parametrize(
    "value",
    [
        ADDRESS,
        "00_11_22_33_44_55",
        "00:11:22:33:44:55",
        "00 11 22 33 44 55",
        "00:11:22:33:44:55.1",
    ],
)
def test_normalize_address(value: str) -> None:
    assert normalize_address(value) == "001122334455"


def test_to_domain_node_preserves_absence_and_empty_values() -> None:
    assert to_domain_node({}) == to_domain_node(
        {
            "node.name": "",
            "media.class": "",
        }
    )
    node = to_domain_node(
        {
            "node.name": "sink",
            "media.class": "Audio/Sink",
            "api.bluez5.profile": "",
            "api.bluez5.codec": "",
            "api.bluez5.transport": "",
        }
    )
    assert node.profile == ""
    assert node.codec == ""
    assert node.transport == ""
    assert node.media_class == "Audio/Sink"


@pytest.mark.parametrize(
    "flat",
    [
        {"api.bluez5.address": ADDRESS, "node.name": "address", "media.class": "Audio/Sink"},
        {"node.name": "bluez_output.00_11_22_33_44_55.1", "media.class": "Audio/Sink"},
        {"device.name": "bluez_card.00_11_22_33_44_55", "media.class": "Audio/Source"},
    ],
)
def test_match_nodes_by_address_uses_all_observed_identifiers(flat: dict[str, str]) -> None:
    assert len(match_nodes_by_address(ADDRESS.lower(), [flat])) == 1


def test_match_nodes_by_address_prefers_exact_property() -> None:
    nodes = [
        {"api.bluez5.address": ADDRESS, "node.name": "exact"},
        {"node.name": "bluez_output.00_11_22_33_44_55.1"},
    ]

    assert [node.node_name for node in match_nodes_by_address(ADDRESS, nodes)] == ["exact"]


def test_match_nodes_by_address_returns_sink_and_source() -> None:
    nodes = [
        {"node.name": "bluez_output.00_11_22_33_44_55.1", "media.class": "Audio/Sink"},
        {"node.name": "bluez_input.00_11_22_33_44_55.1", "media.class": "Audio/Source"},
    ]

    assert len(match_nodes_by_address(ADDRESS, nodes)) == 2
    assert match_nodes_by_address("AA:BB:CC:DD:EE:FF", nodes) == []
