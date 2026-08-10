"""Pruebas para el módulo de configuración."""

from __future__ import annotations

import json
from pathlib import Path

from backend.config import AppConfig, ConfigManager


class TestConfigManager:
    """Pruebas del gestor de configuración."""

    def test_config_manager_creates_default(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        cm = ConfigManager(config_path=config_file)
        assert config_file.exists()
        assert isinstance(cm.get(), AppConfig)

    def test_config_manager_loads_existing(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        data = {
            "app_name": "Test App",
            "version": "9.9.9",
            "logging": {"level": "INFO"},
            "bluetooth": {"scan_timeout": 30},
            "audio": {"prefer_a2dp": False},
            "backup": {"max_backups": 20},
        }
        config_file.write_text(json.dumps(data))
        cm = ConfigManager(config_path=config_file)
        cfg = cm.get()
        assert cfg.app_name == "Test App"
        assert cfg.version == "9.9.9"
        assert cfg.logging.level == "INFO"
        assert cfg.bluetooth.scan_timeout == 30
        assert cfg.audio.prefer_a2dp is False
        assert cfg.backup.max_backups == 20

    def test_config_manager_handles_corrupt_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text("NOT JSON {{{")
        cm = ConfigManager(config_path=config_file)
        cfg = cm.get()
        assert cfg.app_name == "OpenBuds Manager"

    def test_config_save_and_reload(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        cm = ConfigManager(config_path=config_file)
        cm.save()
        cm.reload()
        assert cm.get().app_name == "OpenBuds Manager"
