"""Tests de configuración de la app (carga/guardado TOML)."""

from __future__ import annotations

from pathlib import Path

import pytest

from openbuds.core.config import (
    BACKUP_DIR,
    CONFIG_FILE,
    default_config,
    load_config,
    save_config,
)
from openbuds.core.errors import ConfigError
from openbuds.infrastructure.persistence.app_config import AppConfigStore


class TestDefaultConfig:
    def test_defaults_are_sensible(self) -> None:
        c = default_config()
        assert c.log_level == "INFO"
        assert c.log_file == ""
        assert c.auto_rollback_on_error is True
        assert c.experimental_features is False

    def test_backup_dir_points_to_xdg_data(self) -> None:
        c = default_config()
        assert BACKUP_DIR.as_posix().endswith("openbuds/backups")
        assert c.backup_dir == str(BACKUP_DIR)


class TestLoadConfig:
    def test_missing_file_returns_defaults(self, tmp_path: Path) -> None:
        path = tmp_path / "no_existe.toml"
        assert load_config(path) == default_config()

    def test_empty_file_returns_defaults(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.toml"
        path.write_text("", encoding="utf-8")
        assert load_config(path) == default_config()

    def test_valid_partial_config_merges_with_defaults(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        path.write_text(
            '[openbuds]\nlog_level = "DEBUG"\n',
            encoding="utf-8",
        )
        c = load_config(path)
        assert c.log_level == "DEBUG"  # pisado
        assert c.auto_rollback_on_error is True  # default conservado

    def test_full_config_overrides_all(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        path.write_text(
            "[openbuds]\n"
            'log_level = "WARNING"\n'
            'log_file = "/tmp/openbuds.log"\n'
            'backup_dir = "/tmp/backups"\n'
            "auto_rollback_on_error = false\n"
            "experimental_features = true\n",
            encoding="utf-8",
        )
        c = load_config(path)
        assert c.log_level == "WARNING"
        assert c.log_file == "/tmp/openbuds.log"
        assert c.backup_dir == "/tmp/backups"
        assert c.auto_rollback_on_error is False
        assert c.experimental_features is True

    def test_unknown_fields_are_ignored(self, tmp_path: Path) -> None:
        # Forward-compat: campos desconocidos no rompen la carga.
        path = tmp_path / "config.toml"
        path.write_text(
            '[openbuds]\nlog_level = "ERROR"\nfuture_field = "algo"\n',
            encoding="utf-8",
        )
        c = load_config(path)
        assert c.log_level == "ERROR"

    def test_malformed_toml_raises_config_error(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.toml"
        path.write_text("this is = = not valid toml {{{", encoding="utf-8")
        with pytest.raises(ConfigError):
            load_config(path)

    def test_wrong_type_raises_config_error(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        path.write_text(
            "[openbuds]\nlog_level = 123\n",  # int en vez de str
            encoding="utf-8",
        )
        with pytest.raises(ConfigError):
            load_config(path)

    def test_non_dict_section_raises_config_error(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        path.write_text('openbuds = "no es una tabla"\n', encoding="utf-8")
        with pytest.raises(ConfigError):
            load_config(path)


class TestSaveConfig:
    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "anidado" / "dir" / "config.toml"
        save_config(default_config(), path)
        assert path.exists()

    def test_save_and_reload_roundtrip(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        original = default_config()
        # Modificamos algún campo para verificar la ida y vuelta.
        from dataclasses import replace

        original = replace(original, log_level="DEBUG", experimental_features=True)

        save_config(original, path)
        loaded = load_config(path)

        assert loaded == original

    def test_save_contains_human_readable_comments(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        save_config(default_config(), path)
        content = path.read_text(encoding="utf-8")
        assert "[openbuds]" in content
        assert "log_level" in content
        # Los comentarios explicativos deben estar presentes.
        assert content.startswith("#")


class TestAppConfigStore:
    def test_store_load_returns_defaults_when_missing(self, tmp_path: Path) -> None:
        store = AppConfigStore(tmp_path / "missing.toml")
        assert store.load() == default_config()

    def test_store_save_then_load_roundtrip(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        store = AppConfigStore(path)
        from dataclasses import replace

        config = replace(default_config(), log_level="WARNING")
        store.save(config)
        assert store.load() == config

    def test_default_config_file_path_points_to_xdg(self) -> None:
        # Smoke test: la constante global apunta bajo ~/.config/openbuds/.
        assert CONFIG_FILE.as_posix().endswith(".config/openbuds/config.toml")
