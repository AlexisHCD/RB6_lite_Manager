"""Smoke opt-in del comando ``devices`` contra el BlueZ local."""

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
def test_devices_smoke_is_private_and_returns_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["devices"]) == 0
    captured = capsys.readouterr()

    lines = captured.out.splitlines()
    if lines == ["No se encontraron dispositivos Bluetooth."]:
        pass
    elif lines:
        assert lines[0] == "NOMBRE\tCONEXIÓN\tEMPAREJAMIENTO\tADAPTADOR"
        assert all(len(line.split("\t")) == 4 for line in lines[1:])
    assert re.search(r"[0-9A-F]{2}(?::[0-9A-F]{2}){5}", captured.out) is None
    assert "/org/bluez/" not in captured.out
    assert "dev_" not in captured.out
    assert re.search(r"[0-9A-F]{2}(?::[0-9A-F]{2}){5}", captured.err) is None
    assert "dev_" not in captured.err
