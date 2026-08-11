"""Integración real de solo lectura para ``PwDumpRunner`` y su parser."""

from __future__ import annotations

import os

import pytest

from openbuds.infrastructure.pipewire.pw_dump_parser import parse_bluetooth_audio_nodes
from openbuds.infrastructure.pipewire.pw_dump_runner import PwDumpRunner


@pytest.mark.integration
def test_real_pw_dump_runner_feeds_parser_without_assuming_devices() -> None:
    """Ejecuta el dumper real sin imprimir payloads ni exigir nodos Bluetooth."""
    if os.environ.get("OPENBUDS_RUN_INTEGRATION") != "1":
        pytest.skip("integración PipeWire desactivada; usa OPENBUDS_RUN_INTEGRATION=1")

    payload = PwDumpRunner(timeout_seconds=5.0).dump()
    nodes = parse_bluetooth_audio_nodes(payload)

    assert isinstance(payload, str)
    assert isinstance(nodes, list)
