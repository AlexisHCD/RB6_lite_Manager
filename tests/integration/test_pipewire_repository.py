"""Integración real de solo lectura para ``PipeWireRepository``."""

from __future__ import annotations

import os

import pytest

from openbuds.infrastructure.pipewire.pipewire_repository import PipeWireRepository


@pytest.mark.integration
def test_real_pipewire_repository_lists_nodes_without_assuming_devices() -> None:
    """Compone runner y parser reales sin exigir auriculares conectados."""
    if os.environ.get("OPENBUDS_RUN_INTEGRATION") != "1":
        pytest.skip("integración PipeWire desactivada; usa OPENBUDS_RUN_INTEGRATION=1")

    nodes = PipeWireRepository().list_bluetooth_audio_nodes()

    assert isinstance(nodes, list)
    assert all(isinstance(node, dict) for node in nodes)
    assert all(
        isinstance(key, str) and isinstance(value, str)
        for node in nodes
        for key, value in node.items()
    )
