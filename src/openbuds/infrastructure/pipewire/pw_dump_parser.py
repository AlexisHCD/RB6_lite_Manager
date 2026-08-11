"""Pure parser for Bluetooth audio nodes from ``pw-dump`` JSON output.

The input shape follows the official ``pw-dump(1)`` documentation:
https://docs.pipewire.org/page_man_pw-dump_1.html
"""

from __future__ import annotations

import json
from typing import Any

from openbuds.core.errors import PipeWireParseError


def parse_bluetooth_audio_nodes(payload: str) -> list[dict[str, str]]:
    """Extract and normalize Bluetooth sink/source nodes from a JSON payload.

    Args:
        payload: Complete JSON text emitted by ``pw-dump``.

    Returns:
        Stable, sorted flat dictionaries containing scalar node properties.

    Raises:
        PipeWireParseError: If the JSON is invalid or its root is not a list.

    """
    try:
        root: Any = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise PipeWireParseError("JSON de pw-dump inválido") from exc

    if not isinstance(root, list):
        raise PipeWireParseError("El root JSON de pw-dump debe ser una lista")

    candidates: list[tuple[int, str, dict[str, str]]] = []
    for entry in root:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "PipeWire:Interface:Node":
            continue

        info = entry.get("info")
        if not isinstance(info, dict):
            continue
        props = info.get("props")
        if not isinstance(props, dict):
            continue

        media_class = props.get("media.class")
        if media_class not in ("Audio/Sink", "Audio/Source"):
            continue

        node_name = props.get("node.name")
        is_bluez_name = isinstance(node_name, str) and (
            node_name.startswith("bluez_output.") or node_name.startswith("bluez_input.")
        )
        if not (is_bluez_name or props.get("device.api") == "bluez5"):
            continue

        node_id = entry.get("id")
        if type(node_id) is not int or node_id < 0:
            continue

        flat: dict[str, str] = {}
        for key, value in props.items():
            if not isinstance(key, str):
                continue
            if isinstance(value, str):
                flat[key] = value
            elif isinstance(value, bool):
                flat[key] = "true" if value else "false"
            elif isinstance(value, (int, float)):
                flat[key] = str(value)

        flat["object.id"] = str(node_id)
        sort_name = node_name if isinstance(node_name, str) else ""
        candidates.append((node_id, sort_name, flat))

    candidates.sort(key=lambda item: (item[0], item[1]))
    return [flat for _, _, flat in candidates]
