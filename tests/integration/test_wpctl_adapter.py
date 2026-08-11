"""Integración real de solo lectura para ``WpctlAdapter``."""

from __future__ import annotations

import os

import pytest

from openbuds.infrastructure.wireplumber.wpctl_adapter import WpctlAdapter


@pytest.mark.integration
def test_real_wpctl_status_and_default_sink_inspection_are_read_only() -> None:
    """Consulta WirePlumber real sin imprimir propiedades ni cambiar estado."""
    if os.environ.get("OPENBUDS_RUN_INTEGRATION") != "1":
        pytest.skip("integración WirePlumber desactivada; usa OPENBUDS_RUN_INTEGRATION=1")

    adapter = WpctlAdapter(timeout_seconds=5.0)
    status = adapter.status()
    inspection = adapter.inspect("@DEFAULT_AUDIO_SINK@")

    assert isinstance(status, str)
    assert isinstance(inspection, str)
    assert "node.name" in inspection
    assert "media.class" in inspection
