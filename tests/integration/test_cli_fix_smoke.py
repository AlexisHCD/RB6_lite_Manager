"""Opt-in smoke test for the non-mutating ``openbuds fix`` path."""

from __future__ import annotations

import os

import pytest

from openbuds.cli.main import main


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("OPENBUDS_RUN_INTEGRATION") != "1",
    reason="requiere OPENBUDS_RUN_INTEGRATION=1",
)
def test_unknown_fix_is_reported_without_mutating_services(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = main(["fix", "no-existe"])
    captured = capsys.readouterr()

    assert result == 1
    assert "No hay auto-fix disponible" in captured.out
