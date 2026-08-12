"""Opt-in smoke test for isolated persistent configuration commands."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("OPENBUDS_RUN_INTEGRATION") != "1",
    reason="requires OPENBUDS_RUN_INTEGRATION=1",
)
def test_config_commands_use_isolated_xdg_paths(tmp_path: Path) -> None:
    environment = os.environ.copy()
    source_path = str(Path(__file__).resolve().parents[2] / "src")
    environment["PYTHONPATH"] = os.pathsep.join(
        path for path in (source_path, environment.get("PYTHONPATH", "")) if path
    )
    config_home = tmp_path / "config-home"
    data_home = tmp_path / "data-home"
    environment["XDG_CONFIG_HOME"] = str(config_home)
    environment["XDG_DATA_HOME"] = str(data_home)

    def run(*arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "openbuds.cli.main", *arguments],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            env=environment,
        )

    config_path = config_home / "openbuds" / "config.toml"
    backup_dir = data_home / "openbuds" / "backups"

    initial = run("config", "get")
    assert initial.returncode == 0
    assert "Nivel de log:" in initial.stdout

    dry_run = run("config", "set", "experimental_features", "true", "--dry-run")
    assert dry_run.returncode == 0
    assert "(dry-run: no se escribió nada)" in dry_run.stdout
    assert not config_path.exists()
    assert not backup_dir.exists()

    create_config = run("config", "set", "log_level", "INFO")
    assert create_config.returncode == 0
    assert config_path.exists()

    update_config = run("config", "set", "experimental_features", "true")
    assert update_config.returncode == 0
    assert config_path.exists()
    assert list(backup_dir.glob("*.bak"))

    effective = run("config", "get")
    assert effective.returncode == 0
    assert "Funciones experimentales: sí" in effective.stdout
