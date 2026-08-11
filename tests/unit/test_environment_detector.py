"""Tests unitarios del detector de entorno."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

from openbuds.domain.models import SystemInfo
from openbuds.infrastructure.system import environment_detector as detector


def _supported_info(**changes: object) -> SystemInfo:
    values = {
        "os_id": "ubuntu",
        "os_version": "24.04.3",
        "kernel_version": "6.8.0",
        "bluez_version": "5.72",
        "pipewire_version": "1.0.5",
        "wireplumber_version": "0.4.17",
        "wireplumber_config_style": "lua-0.4",
        "dbus_version": "systemd 255",
        "has_bluetooth_adapter": True,
        "system_bus_available": True,
        "user_config_writable": True,
        "is_supported": True,
    }
    return replace(SystemInfo(**values), **changes)


def test_run_degrada_si_falta_el_binario(monkeypatch) -> None:
    monkeypatch.setattr(
        detector.subprocess,
        "run",
        Mock(side_effect=FileNotFoundError),
    )

    assert detector._run(["no-existe"]) == ""


def test_run_degrada_si_agota_timeout_o_falla_el_comando(monkeypatch) -> None:
    for error in (subprocess.TimeoutExpired("cmd", 1), OSError("fallo")):
        monkeypatch.setattr(detector.subprocess, "run", Mock(side_effect=error))
        assert detector._run(["cmd"]) == ""

    monkeypatch.setattr(
        detector.subprocess,
        "run",
        Mock(return_value=Mock(returncode=1, stdout="versión inválida")),
    )
    assert detector._run(["cmd"]) == ""


def test_run_succeeds_devuelve_true_con_returncode_cero(monkeypatch) -> None:
    monkeypatch.setattr(
        detector.subprocess,
        "run",
        Mock(return_value=Mock(returncode=0)),
    )

    assert detector._run_succeeds(["cmd"])


def test_run_succeeds_devuelve_false_con_returncode_no_cero(monkeypatch) -> None:
    monkeypatch.setattr(
        detector.subprocess,
        "run",
        Mock(return_value=Mock(returncode=1)),
    )

    assert not detector._run_succeeds(["cmd"])


def test_run_succeeds_degrada_ante_errores(monkeypatch) -> None:
    for error in (FileNotFoundError, subprocess.TimeoutExpired("cmd", 1), OSError("fallo")):
        monkeypatch.setattr(detector.subprocess, "run", Mock(side_effect=error))
        assert not detector._run_succeeds(["cmd"])


def test_detecta_wireplumber_via_pkg_config_con_nombre_correcto(monkeypatch) -> None:
    commands: list[list[str]] = []

    def run_command(args: list[str], timeout: float = 5.0) -> str:
        commands.append(args)
        outputs = {
            ("wireplumber", "--version"): "",
            ("pkg-config", "--modversion", "wireplumber-0.4"): "0.4.17",
        }
        return outputs.get(tuple(args), "")

    monkeypatch.setattr(detector, "_run", run_command)
    monkeypatch.setattr(detector, "_detect_os", lambda: ("unknown", "unknown"))
    monkeypatch.setattr(detector.shutil, "which", lambda _: None)
    monkeypatch.setattr(detector, "_run_succeeds", lambda args: False)
    monkeypatch.setattr(detector, "_has_bluetooth_adapter", lambda: False)
    monkeypatch.setattr(detector, "_is_user_config_writable", lambda: False)

    info = detector.detect()

    assert info.wireplumber_version == "0.4.17"
    assert ["pkg-config", "--modversion", "wireplumber-0.4"] in commands
    assert ["pkg-config", "--modversion", "libwireplumber-0.4"] not in commands


def test_detecta_entorno_completo_y_calcula_soporte_sin_comandos_reales(monkeypatch) -> None:
    outputs = {
        ("uname", "-r"): "6.8.0",
        ("bluetoothctl", "--version"): "bluetoothctl: 5.72",
        ("pipewire", "--version"): "Compiled with libpipewire 1.0.5",
        ("wireplumber", "--version"): "wireplumber 0.4.17",
        ("busctl", "--version"): "systemd 255",
    }

    monkeypatch.setattr(detector, "_detect_os", lambda: ("ubuntu", "24.04.3"))
    monkeypatch.setattr(detector, "_run", lambda args: outputs.get(tuple(args), ""))
    monkeypatch.setattr(detector.shutil, "which", lambda _: "/usr/bin/pipewire")
    monkeypatch.setattr(detector, "_run_succeeds", lambda args: True)
    monkeypatch.setattr(detector, "_has_bluetooth_adapter", lambda: True)
    monkeypatch.setattr(detector, "_is_user_config_writable", lambda: True)

    info = detector.detect()

    assert isinstance(info, SystemInfo)
    assert info.is_supported


def test_parsea_versiones_reales_del_stack() -> None:
    assert detector._parse_bluez_version("bluetoothctl: 5.72") == "5.72"
    assert detector._parse_pipewire_version("Compiled with libpipewire 1.0.5") == "1.0.5"
    assert detector._parse_wireplumber_version("Compiled with libwireplumber 0.4.17") == "0.4.17"


def test_wireplumber_fallback_acepta_una_linea_de_version() -> None:
    assert detector._parse_pipewire_version("pipewire 1.0.5") == "1.0.5"
    assert detector._parse_wireplumber_version("wireplumber 0.4.17") == "0.4.17"


def test_estilo_wireplumber_valida_mayor_y_menor() -> None:
    assert detector._detect_wp_config_style("0.4.17") == "lua-0.4"
    assert detector._detect_wp_config_style("0.5.0") == "conf-0.5"
    assert detector._detect_wp_config_style("1.0.0") == "conf-0.5"
    assert detector._detect_wp_config_style("unknown") == "unknown"


def test_detecta_adaptadores_hci_sin_hardware_real(tmp_path: Path) -> None:
    (tmp_path / "hci0").mkdir()
    (tmp_path / "README").touch()

    assert detector._has_bluetooth_adapter(tmp_path)
    assert not detector._has_bluetooth_adapter(tmp_path / "missing")


def test_permiso_de_configuracion_usa_ancestro_existente(tmp_path: Path, monkeypatch) -> None:
    existing = tmp_path / "config"
    existing.mkdir()
    config_path = existing / "openbuds"
    monkeypatch.setattr(detector.os, "access", lambda path, mode: path == existing)

    assert detector._is_user_config_writable(config_path)


def test_soporte_exige_todos_los_minimos() -> None:
    info = _supported_info()
    assert detector._is_system_supported(info)
    for field in (
        "os_id",
        "os_version",
        "bluez_version",
        "pipewire_version",
        "wireplumber_version",
        "wireplumber_config_style",
        "system_bus_available",
    ):
        value = "unknown" if isinstance(getattr(info, field), str) else False
        assert not detector._is_system_supported(replace(info, **{field: value}))


def test_soporte_no_depende_de_hardware_ni_configuracion() -> None:
    info = _supported_info(has_bluetooth_adapter=False, user_config_writable=False)

    assert detector._is_system_supported(info)


def test_runtime_no_listo_con_base_prefix_linuxbrew_sin_importar_gio(monkeypatch) -> None:
    monkeypatch.setattr(detector.sys, "base_prefix", "/home/linuxbrew/.linuxbrew")

    assert not detector.is_runtime_ready()


def test_runtime_listo_con_imports_fake(monkeypatch) -> None:
    fake_gi = ModuleType("gi")
    fake_repository = ModuleType("gi.repository")
    require_version = Mock()
    fake_repository.__dict__.update({"Gio": object(), "GLib": object()})
    fake_gi.__dict__.update({"repository": fake_repository, "require_version": require_version})
    monkeypatch.setattr(detector.sys, "base_prefix", "/usr")
    monkeypatch.setitem(sys.modules, "gi", fake_gi)
    monkeypatch.setitem(sys.modules, "gi.repository", fake_repository)

    assert detector.is_runtime_ready()
    require_version.assert_called_once_with("Gio", "2.0")


def test_runtime_no_listo_con_import_gi_fallido(monkeypatch) -> None:
    monkeypatch.setattr(detector.sys, "base_prefix", "/usr")
    monkeypatch.setitem(sys.modules, "gi", None)

    assert not detector.is_runtime_ready()


def test_doctor_muestra_bus_permisos_y_devuelve_estado(monkeypatch, capsys) -> None:
    from openbuds.cli import main as cli

    info = _supported_info()
    from openbuds.core import logging_setup

    monkeypatch.setattr(logging_setup, "setup_logging", lambda level: None)
    monkeypatch.setattr(detector, "detect", lambda: info)
    monkeypatch.setattr(detector, "is_runtime_ready", lambda: True)

    assert cli.main(["doctor"]) == 0
    output = capsys.readouterr().out
    assert "Bus del sistema:" in output
    assert "Configuración usuario:" in output


def test_doctor_devuelve_uno_si_el_entorno_no_esta_soportado(monkeypatch) -> None:
    from openbuds.cli import main as cli
    from openbuds.core import logging_setup

    monkeypatch.setattr(logging_setup, "setup_logging", lambda level: None)
    monkeypatch.setattr(detector, "detect", lambda: _supported_info(is_supported=False))
    monkeypatch.setattr(detector, "is_runtime_ready", lambda: True)

    assert cli.main(["doctor"]) == 1
