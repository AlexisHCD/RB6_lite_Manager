"""Opt-in smoke test for the real read-only ``openbuds logs`` command."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("OPENBUDS_RUN_INTEGRATION") != "1",
    reason="requires OPENBUDS_RUN_INTEGRATION=1",
)
def test_logs_smoke_is_private_and_returns_a_coherent_exit_code() -> None:
    environment = os.environ.copy()
    source_path = str(Path(__file__).resolve().parents[2] / "src")
    environment["PYTHONPATH"] = os.pathsep.join(
        path for path in (source_path, environment.get("PYTHONPATH", "")) if path
    )
    completed = subprocess.run(
        [sys.executable, "-m", "openbuds.cli.main", "logs", "--lines", "5"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
        env=environment,
    )
    output = completed.stdout
    error = completed.stderr
    combined = output + error
    forbidden_address = ":".join(("78", "99", "87", "E8", "6D", "05"))

    assert completed.returncode in {0, 1}
    assert forbidden_address not in combined
    assert re.search(r"[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}", combined) is None
    assert "/org/bluez/" not in combined
    assert (
        any(f"=== {service} ===" in output for service in ("bluez", "wireplumber", "pipewire"))
        or "(no disponible:" in output
    )
