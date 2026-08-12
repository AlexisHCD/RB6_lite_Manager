"""Opt-in lifecycle smoke test for the ``watch`` subscription."""

from __future__ import annotations

import os
import time

import pytest

from openbuds.application.watch_devices import WatchDevicesUseCase
from openbuds.infrastructure.bluez.bluez_repository import BlueZRepository


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("OPENBUDS_RUN_INTEGRATION") != "1",
    reason="requires OPENBUDS_RUN_INTEGRATION=1",
)
def test_watch_subscription_lifecycle_does_not_hang() -> None:
    unsubscribe = WatchDevicesUseCase(BlueZRepository()).subscribe(lambda _event: None)
    time.sleep(0.5)
    unsubscribe()
