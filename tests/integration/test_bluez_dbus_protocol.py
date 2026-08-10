from __future__ import annotations

import os

import pytest

from openbuds.infrastructure.bluez.dbus_client import BlueZDBusClient


@pytest.mark.integration
def test_real_bluez_snapshot_is_read_only_and_coherent() -> None:
    if os.environ.get("OPENBUDS_RUN_INTEGRATION") != "1":
        pytest.skip("integración BlueZ desactivada; usa OPENBUDS_RUN_INTEGRATION=1")

    snapshot = BlueZDBusClient().snapshot()

    assert isinstance(snapshot, dict)
    assert snapshot
    assert any(snapshot_path and interfaces for snapshot_path, interfaces in snapshot.items())
