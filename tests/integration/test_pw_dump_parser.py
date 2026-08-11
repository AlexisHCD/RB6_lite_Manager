"""Prueba de integración de solo lectura para el parser de ``pw-dump``."""

from __future__ import annotations

import os
import shutil
import subprocess

import pytest

from openbuds.infrastructure.pipewire.pw_dump_parser import parse_bluetooth_audio_nodes


@pytest.mark.integration
def test_real_pw_dump_bluetooth_audio_nodes_are_well_formed() -> None:
    """Parsea el estado local de PipeWire sin exigir dispositivos conectados."""
    if os.environ.get("OPENBUDS_RUN_INTEGRATION") != "1":
        pytest.skip("integración PipeWire desactivada; usa OPENBUDS_RUN_INTEGRATION=1")

    binary = shutil.which("pw-dump")
    if binary is None:
        pytest.skip("pw-dump no está instalado")
    assert binary is not None

    try:
        completed = subprocess.run(
            [binary, "--no-colors"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except subprocess.CalledProcessError as exc:
        pytest.fail(f"pw-dump terminó con código {exc.returncode}")
        return
    except subprocess.TimeoutExpired:
        pytest.fail("pw-dump excedió el tiempo límite de 5 segundos")
        return

    nodes = parse_bluetooth_audio_nodes(completed.stdout)
    assert isinstance(nodes, list)

    for node in nodes:
        assert isinstance(node, dict)
        assert node
        assert all(isinstance(key, str) and isinstance(value, str) for key, value in node.items())

        object_id = node.get("object.id")
        assert object_id is not None and object_id.isdigit() and int(object_id) >= 0
        assert node.get("media.class") in {"Audio/Sink", "Audio/Source"}

        node_name = node.get("node.name", "")
        device_api = node.get("device.api")
        assert node_name.startswith(("bluez_output.", "bluez_input.")) or device_api == "bluez5"
