from __future__ import annotations

import os
import threading

import pytest

from openbuds.infrastructure.bluez.dbus_client import BlueZDBusClient
from openbuds.infrastructure.bluez.dbus_protocol import SignalEvent


@pytest.mark.integration
def test_real_bluez_signal_lifecycle_preserves_shared_bus() -> None:
    if os.environ.get("OPENBUDS_RUN_INTEGRATION") != "1":
        pytest.skip("integración BlueZ desactivada; usa OPENBUDS_RUN_INTEGRATION=1")

    poll_called = threading.Event()

    def dummy_callback(_event: SignalEvent) -> None:
        pass

    client = BlueZDBusClient()
    subscription_id: int | None = None
    try:
        subscription_id = client.subscribe(
            dummy_callback,
            on_poll=poll_called.set,
            poll_interval_ms=60_000,
        )
        assert subscription_id > 0
        client.unsubscribe(subscription_id)
        assert not poll_called.is_set()
        client.unsubscribe(subscription_id)
        assert not poll_called.is_set()
    finally:
        try:
            if subscription_id is not None:
                client.unsubscribe(subscription_id)
        finally:
            client.close()
            client.close()

    fresh_client = BlueZDBusClient()
    try:
        snapshot = fresh_client.snapshot()
        assert isinstance(snapshot, dict)
    finally:
        fresh_client.close()
