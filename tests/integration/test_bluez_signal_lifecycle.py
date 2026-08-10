from __future__ import annotations

import os

import pytest

from openbuds.infrastructure.bluez.dbus_client import BlueZDBusClient
from openbuds.infrastructure.bluez.dbus_protocol import SignalEvent


@pytest.mark.integration
def test_real_bluez_signal_lifecycle_preserves_shared_bus() -> None:
    if os.environ.get("OPENBUDS_RUN_INTEGRATION") != "1":
        pytest.skip("integración BlueZ desactivada; usa OPENBUDS_RUN_INTEGRATION=1")

    def dummy_callback(_event: SignalEvent) -> None:
        pass

    for _ in range(25):
        client = BlueZDBusClient()
        try:
            subscription_id = client.subscribe(dummy_callback)
            assert subscription_id > 0
            client.unsubscribe(subscription_id)
            client.close()
            client.close()
        except BaseException:
            client.close()
            raise

    fresh_client = BlueZDBusClient()
    try:
        snapshot = fresh_client.snapshot()
        assert isinstance(snapshot, dict)
    finally:
        fresh_client.close()
