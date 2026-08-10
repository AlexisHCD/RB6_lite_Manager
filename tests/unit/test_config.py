"""Tests de configuración de la app (carga/guardado TOML)."""

from __future__ import annotations

from pathlib import Path

import pytest

from openbuds.core.config import (
    BACKUP_DIR,
    CONFIG_DIR,
    CONFIG_FILE,
    default_config,
    load_config,
    resolve_xdg_home,
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


class TestXdgPaths:
    @pytest.mark.parametrize("variable", ["XDG_CONFIG_HOME", "XDG_DATA_HOME"])
    @pytest.mark.parametrize("value", [None, "", "relative/path"])
    def test_invalid_xdg_value_uses_fallback(
        self,
        monkeypatch: pytest.MonkeyPatch,
        variable: str,
        value: str | None,
    ) -> None:
        if value is None:
            monkeypatch.delenv(variable, raising=False)
        else:
            monkeypatch.setenv(variable, value)

        fallback = Path("/home/test/.config")
        assert resolve_xdg_home(variable, fallback) == fallback

    @pytest.mark.parametrize("variable", ["XDG_CONFIG_HOME", "XDG_DATA_HOME"])
    def test_absolute_xdg_value_is_used(
        self, monkeypatch: pytest.MonkeyPatch, variable: str
    ) -> None:
        monkeypatch.setenv(variable, "/tmp/test-xdg")

        assert resolve_xdg_home(variable, Path("/home/test/fallback")) == Path("/tmp/test-xdg")


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

    def test_read_oserror_raises_config_error_with_cause(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "unreadable.toml"
        path.write_text("[openbuds]\n", encoding="utf-8")

        def fail_open(*args: object, **kwargs: object) -> object:
            raise OSError("lectura denegada")

        monkeypatch.setattr(Path, "open", fail_open)

        with pytest.raises(ConfigError, match=str(path)) as raised:
            load_config(path)
        assert isinstance(raised.value.__cause__, OSError)

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

    def test_save_roundtrips_special_and_unicode_strings(self, tmp_path: Path) -> None:
        from dataclasses import replace

        path = tmp_path / "config.toml"
        original = replace(
            default_config(),
            log_level='D"EBUG\\special\nline',
            log_file="/tmp/á\t.log",
            backup_dir='C:\\backups\\"quoted"',
        )

        save_config(original, path)

        assert load_config(path) == original

    def test_mkdir_failure_raises_config_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "missing" / "config.toml"

        def fail_mkdir(*args: object, **kwargs: object) -> None:
            raise OSError("mkdir denegado")

        monkeypatch.setattr(Path, "mkdir", fail_mkdir)

        with pytest.raises(ConfigError, match=str(path)) as raised:
            save_config(default_config(), path)
        assert isinstance(raised.value.__cause__, OSError)

    def test_replace_failure_preserves_previous_file_and_cleans_temp(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "config.toml"
        path.write_text("previous", encoding="utf-8")

        def fail_replace(*args: object, **kwargs: object) -> None:
            raise OSError("replace denegado")

        monkeypatch.setattr("openbuds.core.config.os.replace", fail_replace)

        with pytest.raises(ConfigError, match=str(path)):
            save_config(default_config(), path)

        assert path.read_text(encoding="utf-8") == "previous"
        assert list(tmp_path.glob(f".{path.name}.*.tmp")) == []

    def test_write_failure_preserves_previous_file_and_cleans_temp(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "config.toml"
        path.write_text("previous", encoding="utf-8")

        def fail_fsync(*args: object) -> None:
            raise OSError("fsync denegado")

        monkeypatch.setattr("openbuds.core.config.os.fsync", fail_fsync)

        with pytest.raises(ConfigError, match=str(path)):
            save_config(default_config(), path)

        assert path.read_text(encoding="utf-8") == "previous"
        assert list(tmp_path.glob(f".{path.name}.*.tmp")) == []

    def test_success_leaves_no_temporary_files(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"

        save_config(default_config(), path)

        assert list(tmp_path.glob(f".{path.name}.*.tmp")) == []


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
        assert CONFIG_FILE == CONFIG_DIR / "config.toml"
        assert CONFIG_FILE.is_absolute()
