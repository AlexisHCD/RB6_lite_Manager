"""Tests unitarios del parser puro de nodos Bluetooth de ``pw-dump``."""

from __future__ import annotations

import copy
import json

import pytest

from openbuds.core.errors import PipeWireParseError
from openbuds.infrastructure.pipewire.pw_dump_parser import parse_bluetooth_audio_nodes

_MISSING = object()


def _node(
    node_id: object = 1,
    *,
    node_name: object = "bluez_output.AA",
    media_class: object = "Audio/Sink",
    device_api: object = None,
    props: object = None,
    info: object = _MISSING,
    node_type: object = "PipeWire:Interface:Node",
) -> dict[str, object]:
    node_props: dict[object, object] = {
        "media.class": media_class,
        "node.name": node_name,
    }
    if device_api is not None:
        node_props["device.api"] = device_api
    if isinstance(props, dict):
        node_props.update(props)
    node_info = {"props": node_props} if info is _MISSING else info
    node = {"id": node_id, "type": node_type}
    node["info"] = node_info
    return node


def _payload(*entries: object) -> str:
    return json.dumps(list(entries))


def test_invalid_json_is_wrapped_and_chains_json_decode_error() -> None:
    with pytest.raises(PipeWireParseError, match="JSON") as raised:
        parse_bluetooth_audio_nodes("no json")

    assert isinstance(raised.value.__cause__, json.JSONDecodeError)


@pytest.mark.parametrize("root", [{}, None, True, 123])
def test_non_list_json_root_is_rejected(root: object) -> None:
    with pytest.raises(PipeWireParseError, match="root"):
        parse_bluetooth_audio_nodes(json.dumps(root))


def test_empty_root_and_non_dict_entries_are_ignored() -> None:
    assert parse_bluetooth_audio_nodes("[]") == []
    assert parse_bluetooth_audio_nodes(_payload(None, "x", 42, [1], True)) == []


def test_non_node_types_and_malformed_node_structure_are_ignored() -> None:
    other_types = [
        {"type": kind, "id": 1}
        for kind in ("Client", "Device", "Port", "Link", "Module", "Metadata")
    ]
    malformed = [
        _node(node_type=None),
        {"id": 1},
        _node(info=None, node_type="PipeWire:Interface:Node"),
    ]
    malformed.extend(_node(info=info) for info in (None, [], {"props": None}, {"props": []}))

    assert parse_bluetooth_audio_nodes(_payload(*other_types, *malformed)) == []


def test_only_exact_audio_classes_and_bluetooth_markers_are_included() -> None:
    valid = [
        _node(4, node_name="bluez_output.AA"),
        _node(5, node_name="bluez_input.AA", media_class="Audio/Source"),
        _node(6, node_name="custom-node", device_api="bluez5"),
    ]
    invalid = [
        _node(7, node_name="bluez_midi.AA"),
        _node(8, node_name="unrelated.AA"),
        _node(9, node_name="Bluez_output.AA"),
        _node(10, node_name="bluez_output.AA", media_class="Audio/Duplex"),
        _node(11, node_name="bluez_output.AA", media_class=None),
        _node(12, node_name="bluez_output.AA", media_class="Midi/Bridge"),
        _node(13, node_name="custom-node", device_api="Bluez5"),
        _node(14, node_name="custom-node", device_api=None),
        _node(15, node_name="custom-node", device_api="other"),
    ]

    result = parse_bluetooth_audio_nodes(_payload(*valid, *invalid))

    assert [item["object.id"] for item in result] == ["4", "5", "6"]


def test_non_string_node_name_can_use_device_api_fallback() -> None:
    assert parse_bluetooth_audio_nodes(_payload(_node(1, node_name=42, device_api="bluez5"))) == [
        {
            "object.id": "1",
            "media.class": "Audio/Sink",
            "node.name": "42",
            "device.api": "bluez5",
        }
    ]


@pytest.mark.parametrize("node_id", [None, True, -1, "12", 3.0])
def test_invalid_ids_are_ignored(node_id: object) -> None:
    assert parse_bluetooth_audio_nodes(_payload(_node(node_id))) == []


def test_zero_is_a_valid_id() -> None:
    assert parse_bluetooth_audio_nodes(_payload(_node(0))) == [
        {"object.id": "0", "media.class": "Audio/Sink", "node.name": "bluez_output.AA"}
    ]


def test_scalar_properties_are_normalized_and_complex_values_ignored() -> None:
    props = {
        "exact": "  Mixed Case  ",
        "enabled": True,
        "disabled": False,
        "rate": 48000,
        "gain": 1.5,
        "null_value": None,
        "list_value": [1, 2],
        "dict_value": {"nested": True},
        "bluez5.codec": "vendor codec / exact",
        "api.bluez5.transport": "transport?verbatim",
        "id": "props-id",
    }

    result = parse_bluetooth_audio_nodes(_payload(_node(27, props=props)))

    assert result == [
        {
            "object.id": "27",
            "media.class": "Audio/Sink",
            "node.name": "bluez_output.AA",
            "exact": "  Mixed Case  ",
            "enabled": "true",
            "disabled": "false",
            "rate": "48000",
            "gain": "1.5",
            "bluez5.codec": "vendor codec / exact",
            "api.bluez5.transport": "transport?verbatim",
            "id": "props-id",
        }
    ]
    assert result[0]["object.id"] == "27"
    assert all(isinstance(value, str) for value in result[0].values())


def test_props_with_only_required_fields_yields_no_extra_properties() -> None:
    node = _node(25, props={"media.class": "Audio/Sink", "node.name": "bluez_output.AA"})
    assert parse_bluetooth_audio_nodes(_payload(node)) == [
        {"object.id": "25", "media.class": "Audio/Sink", "node.name": "bluez_output.AA"}
    ]


def test_non_string_property_key_is_outside_json_input_boundary() -> None:
    # json.dumps coerces an integer key to text; JSON cannot preserve this case.
    props: dict[object, object] = {
        "media.class": "Audio/Sink",
        "node.name": "bluez_output.AA",
        7: "ignored",
    }
    payload = json.dumps([_node(1, props=props)])
    assert "7" in json.loads(payload)[0]["info"]["props"]


def test_results_are_sorted_by_numeric_id_then_name_and_keep_duplicates() -> None:
    nodes = [
        _node(2, node_name="bluez_output.Z.AA"),
        _node(1, node_name="bluez_output.AA"),
        _node(2, node_name="bluez_input.AA"),
        _node(2, node_name="bluez_input.AA"),
        _node(10, node_name="bluez_output.AA"),
    ]
    result = parse_bluetooth_audio_nodes(_payload(*nodes))

    assert [(item["object.id"], item["node.name"]) for item in result] == [
        ("1", "bluez_output.AA"),
        ("2", "bluez_input.AA"),
        ("2", "bluez_input.AA"),
        ("2", "bluez_output.Z.AA"),
        ("10", "bluez_output.AA"),
    ]


def test_input_fixture_is_not_mutated_and_output_dicts_are_independent() -> None:
    fixture = [_node(1), _node(2)]
    original = copy.deepcopy(fixture)
    result = parse_bluetooth_audio_nodes(json.dumps(fixture))

    assert fixture == original
    result[0]["new"] = "value"
    assert "new" not in result[1]
