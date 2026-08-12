"""Opt-in smoke test for the real read-only ``openbuds health`` command."""

from __future__ import annotations

import os
import re

import pytest

from openbuds.cli.main import main


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("OPENBUDS_RUN_INTEGRATION") != "1",
    reason="requiere OPENBUDS_RUN_INTEGRATION=1",
)
def test_health_smoke_is_private_and_returns_a_coherent_exit_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = main(["health"])
    captured = capsys.readouterr()

    assert result in {0, 1}
    assert "Estado global:" in captured.out
    assert re.search(r"[0-9A-F]{2}(?::[0-9A-F]{2}){5}", captured.out) is None
    assert re.search(r"[0-9A-F]{2}(?::[0-9A-F]{2}){5}", captured.err) is None
    assert "/org/bluez/" not in captured.out
    assert "/org/bluez/" not in captured.err
    assert "dev_" not in captured.out
    assert "dev_" not in captured.err
