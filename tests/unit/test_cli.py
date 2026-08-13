"""Tests del contrato base de la CLI."""

from __future__ import annotations

import sys
import threading
import time
import types
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

import openbuds.cli.main as cli
import openbuds.core.config as config_module
from openbuds import __version__
from openbuds.application.get_device_info import DeviceAggregate
from openbuds.core.config import CONFIG_FILE, backup_config_file, default_config, load_config
from openbuds.core.errors import ConfigError, OpenBudsError
from openbuds.domain.enums import (
    AddressType,
    BluetoothProfile,
    CheckSeverity,
    CodecType,
    ConnectionState,
    DeviceChangeKind,
    DeviceIcon,
    EvidenceKind,
    HealthStatus,
)
from openbuds.domain.models import (
    BluetoothAudioNode,
    CheckResult,
    CodecInfo,
    DeviceChangeEvent,
    DeviceInfo,
    HealthReport,
    ServiceLogs,
    SystemInfo,
)


def _system_info(supported: bool = True) -> SystemInfo:
    return SystemInfo(
        os_id="ubuntu",
        os_version="24.04",
        kernel_version="6.8.0",
        bluez_version="5.72",
        pipewire_version="1.0.0",
        wireplumber_version="0.4.17",
        wireplumber_config_style="lua-0.4",
        dbus_version="systemd 255",
        has_bluetooth_adapter=True,
        system_bus_available=True,
        user_config_writable=True,
        is_supported=supported,
    )


def test_version_does_not_bootstrap(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "load_config", pytest.fail)
    monkeypatch.setattr(cli, "setup_logging_from_config", pytest.fail)

    assert cli.main(["version"]) == 0
    assert capsys.readouterr().out == f"OpenBuds Manager {__version__}\n"


def test_config_prints_effective_values_without_writing(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = replace(
        default_config(),
        log_level="DEBUG",
        log_file="",
        backup_dir=str(tmp_path / "backups"),
        auto_rollback_on_error=False,
        experimental_features=True,
    )
    monkeypatch.setattr(cli, "load_config", lambda: config)
    monkeypatch.setattr(cli, "setup_logging_from_config", lambda _config: None)

    assert cli.main(["config"]) == 0
    output = capsys.readouterr().out
    assert "Nivel de log: DEBUG" in output
    assert "Archivo de log: stderr" in output
    assert f"CONFIG_FILE: {CONFIG_FILE}" in output
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("supported, expected", [(True, 0), (False, 1)])
def test_doctor_bootstraps_once_and_returns_detector_status(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    supported: bool,
    expected: int,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(cli, "load_config", lambda: calls.append("load") or default_config())
    monkeypatch.setattr(cli, "setup_logging_from_config", lambda _config: calls.append("logging"))
    monkeypatch.setattr(cli.environment_detector, "detect", lambda: _system_info(supported))
    monkeypatch.setattr(cli.environment_detector, "is_runtime_ready", lambda: True)

    assert cli.main(["doctor"]) == expected
    assert calls == ["load", "logging"]
    assert "Sistema soportado:" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("supported", "runtime_ready", "has_adapter", "expected"),
    [(True, True, True, 0), (True, True, False, 0), (True, False, True, 1), (False, True, True, 1)],
)
def test_doctor_exit_depends_on_system_and_runtime_not_hardware(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    supported: bool,
    runtime_ready: bool,
    has_adapter: bool,
    expected: int,
) -> None:
    info = replace(_system_info(supported), has_bluetooth_adapter=has_adapter)
    detect = Mock(return_value=info)
    runtime = Mock(return_value=runtime_ready)
    monkeypatch.setattr(cli, "load_config", lambda: default_config())
    monkeypatch.setattr(cli, "setup_logging_from_config", lambda _config: None)
    monkeypatch.setattr(cli.environment_detector, "detect", detect)
    monkeypatch.setattr(cli.environment_detector, "is_runtime_ready", runtime)

    assert cli.main(["doctor"]) == expected
    output = capsys.readouterr().out
    assert "Sistema soportado: " in output
    assert "Runtime aplicación: " in output
    assert "Hardware Bluetooth: " in output
    detect.assert_called_once_with()
    runtime.assert_called_once_with()


def test_config_error_from_load_is_reported(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        cli,
        "load_config",
        lambda: (_ for _ in ()).throw(ConfigError("config inválida")),
    )

    assert cli.main(["config"]) == 1
    assert capsys.readouterr().err == "Error: config inválida\n"


def test_config_set_updates_string_and_creates_backup(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.toml"
    backup_dir = tmp_path / "backups"
    config_path.write_text('[openbuds]\nlog_level = "INFO"\n', encoding="utf-8")
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)
    monkeypatch.setattr(cli, "BACKUP_DIR", backup_dir)
    monkeypatch.setattr(config_module, "BACKUP_DIR", backup_dir)
    monkeypatch.setattr(cli, "setup_logging_from_config", lambda _config: None)

    assert cli.main(["config", "set", "log_level", "DEBUG"]) == 0

    assert load_config(config_path).log_level == "DEBUG"
    backups = list(backup_dir.glob("*.bak"))
    assert len(backups) == 1
    assert "Configuración guardada (backup:" in capsys.readouterr().out


def test_config_set_rejects_invalid_boolean(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cli, "CONFIG_FILE", tmp_path / "config.toml")
    monkeypatch.setattr(cli, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(cli, "setup_logging_from_config", lambda _config: None)

    assert cli.main(["config", "set", "experimental_features", "maybe"]) == 1

    assert "valor booleano no válido" in capsys.readouterr().err
    assert not (tmp_path / "config.toml").exists()


def test_config_set_dry_run_does_not_write(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.toml"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)
    monkeypatch.setattr(cli, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(cli, "setup_logging_from_config", lambda _config: None)

    assert cli.main(["config", "set", "experimental_features", "true", "--dry-run"]) == 0

    output = capsys.readouterr().out
    assert "experimental_features = true" in output
    assert "(dry-run: no se escribió nada)" in output
    assert not config_path.exists()
    assert not (tmp_path / "backups").exists()


def test_config_backup_creates_a_manual_backup(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.toml"
    backup_dir = tmp_path / "backups"
    config_path.write_text('[openbuds]\nlog_level = "INFO"\n', encoding="utf-8")
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)
    monkeypatch.setattr(cli, "BACKUP_DIR", backup_dir)
    monkeypatch.setattr(cli, "setup_logging_from_config", lambda _config: None)

    assert cli.main(["config", "backup"]) == 0

    assert len(list(backup_dir.glob("*.bak"))) == 1
    assert "Backup creado:" in capsys.readouterr().out


def test_config_restore_restores_selected_backup(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.toml"
    backup_dir = tmp_path / "backups"
    config_path.write_text('[openbuds]\nlog_level = "INFO"\n', encoding="utf-8")
    backup = backup_config_file(config_path, backup_dir)
    config_path.write_text("malformed = = toml", encoding="utf-8")
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)
    monkeypatch.setattr(cli, "BACKUP_DIR", backup_dir)
    monkeypatch.setattr(cli, "setup_logging_from_config", lambda _config: None)

    assert cli.main(["config", "restore", str(backup)]) == 0

    assert load_config(config_path).log_level == "INFO"
    assert "Configuración restaurada desde:" in capsys.readouterr().out


def test_config_backups_lists_files_or_reports_empty(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.toml"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup = backup_dir / "config.20260812-120000.bak"
    backup.write_text("backup", encoding="utf-8")
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)
    monkeypatch.setattr(cli, "BACKUP_DIR", backup_dir)
    monkeypatch.setattr(cli, "setup_logging_from_config", lambda _config: None)

    assert cli.main(["config", "backups"]) == 0

    output = capsys.readouterr().out
    assert str(backup) in output
    assert "bytes" in output


def test_config_get_subcommand_prints_effective_values(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('[openbuds]\nlog_level = "DEBUG"\n', encoding="utf-8")
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)
    monkeypatch.setattr(cli, "setup_logging_from_config", lambda _config: None)

    assert cli.main(["config", "get"]) == 0

    assert "Nivel de log: DEBUG" in capsys.readouterr().out


def test_gui_parser_and_handler_use_lazy_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = cli.build_parser()
    assert parser.parse_args(["gui"]).command == "gui"

    calls: list[str] = []
    fake_module = types.ModuleType("openbuds.presentation.qt.main_window")
    fake_module.run_app = lambda: calls.append("run") or 0  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openbuds.presentation.qt.main_window", fake_module)
    monkeypatch.setattr(cli, "load_config", lambda: default_config())
    monkeypatch.setattr(cli, "setup_logging_from_config", lambda _config: None)

    assert cli.main(["gui"]) == 0
    assert calls == ["run"]


def test_handler_openbuds_error_is_reported(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "load_config", lambda: default_config())
    monkeypatch.setattr(cli, "setup_logging_from_config", lambda _config: None)
    monkeypatch.setattr(
        cli,
        "_cmd_config",
        lambda _context: (_ for _ in ()).throw(OpenBudsError("fallo")),
    )

    assert cli.main(["config"]) == 1
    assert "Error: fallo\n" in capsys.readouterr().err


def test_unexpected_error_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "load_config", lambda: default_config())
    monkeypatch.setattr(cli, "setup_logging_from_config", lambda _config: None)
    monkeypatch.setattr(
        cli,
        "_cmd_config",
        lambda _context: (_ for _ in ()).throw(RuntimeError("bug")),
    )

    with pytest.raises(RuntimeError, match="bug"):
        cli.main(["config"])


@pytest.mark.parametrize(
    ("command", "milestone"),
    [
        ("codec", "Etapa 2 (sujeto a evidencia de la Etapa 1)"),
        ("bench", "una etapa posterior"),
    ],
)
def test_future_command_returns_two_with_real_milestone(
    capsys: pytest.CaptureFixture[str], command: str, milestone: str
) -> None:
    assert cli.main([command]) == 2
    error = capsys.readouterr().err
    assert milestone in error
    assert "no está implementado" in error


class _HealthUseCase:
    def __init__(self, report: HealthReport | Exception) -> None:
        self.report = report

    def execute(self) -> HealthReport:
        if isinstance(self.report, Exception):
            raise self.report
        return self.report


def _health_report(status: HealthStatus) -> HealthReport:
    return HealthReport(
        overall_status=status,
        checks=(
            CheckResult(
                "system.os",
                "Sistema operativo",
                CheckSeverity.OK,
                "Ubuntu 24.04 soportado",
                evidence=EvidenceKind.OBSERVED,
            ),
            CheckResult(
                "audio.sink_default",
                "Sink por defecto del sistema",
                CheckSeverity.WARNING if status is HealthStatus.WARNING else CheckSeverity.ERROR,
                "sin sink por defecto",
                detail="bluez_output.00:11:22:33:44:55.1",
                evidence=EvidenceKind.NOT_AVAILABLE,
            ),
        ),
        recommendations=("Activa Música (A2DP) con openbuds music para mejor calidad",),
        generated_at="2026-08-11T00:00:00+00:00",
    )


def _run_health(
    monkeypatch: pytest.MonkeyPatch,
    use_case: _HealthUseCase,
) -> int:
    monkeypatch.setattr(cli, "load_config", lambda: default_config())
    monkeypatch.setattr(cli, "setup_logging_from_config", lambda _config: None)
    monkeypatch.setattr(cli._LOGGER, "error", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "_build_health_check_use_case", lambda: use_case)
    return cli.main(["health"])


def test_health_prints_evidence_recommendations_and_private_fields(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _run_health(monkeypatch, _HealthUseCase(_health_report(HealthStatus.WARNING)))
    output = capsys.readouterr().out

    assert result == 0
    assert "Estado global: Con advertencias" in output
    assert "[OK]" in output
    assert "[WARN]" in output
    assert "(observado)" in output
    assert "Recomendaciones:" in output
    assert "openbuds music" in output
    assert "00:11:22:33:44:55" not in output
    assert "/org/bluez/" not in output


def test_health_prints_available_fix_id(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    report = _health_report(HealthStatus.WARNING)
    checks = tuple(
        replace(
            check,
            auto_fix_available=True,
            auto_fix_id="start.audio",
        )
        if check.check_id == "audio.sink_default"
        else check
        for check in report.checks
    )
    result = _run_health(
        monkeypatch,
        _HealthUseCase(replace(report, checks=checks)),
    )

    assert result == 0
    assert "[fix: start.audio]" in capsys.readouterr().out


def test_health_error_returns_one(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _run_health(monkeypatch, _HealthUseCase(_health_report(HealthStatus.ERROR)))

    assert result == 1
    assert "Estado global: Error" in capsys.readouterr().out


def test_health_openbuds_error_uses_cli_error_contract(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _run_health(monkeypatch, _HealthUseCase(OpenBudsError("health failed")))

    assert result == 1
    assert capsys.readouterr().err == "Error: health failed\n"


class _FixHealthUseCase:
    def __init__(self, reports: list[HealthReport]) -> None:
        self.reports = reports
        self.calls = 0

    def execute(self) -> HealthReport:
        report = self.reports[min(self.calls, len(self.reports) - 1)]
        self.calls += 1
        return report


class _FixUseCase:
    def __init__(self) -> None:
        self.requests: list[object] = []

    def execute(self, request: object) -> str:
        self.requests.append(request)
        return "fix applied"


class _FixScan:
    def __init__(self, devices: list[DeviceInfo]) -> None:
        self.devices = devices

    def execute(self, _request: object) -> list[DeviceInfo]:
        return self.devices


def _fix_report(
    fix_id: str,
    *,
    check_id: str = "audio.sink_default",
    message: str = "sin sink por defecto",
) -> HealthReport:
    return HealthReport(
        overall_status=HealthStatus.WARNING,
        checks=(
            CheckResult(
                check_id,
                "Check de audio",
                CheckSeverity.WARNING,
                message,
                auto_fix_available=True,
                auto_fix_id=fix_id,
                evidence=EvidenceKind.NOT_AVAILABLE,
            ),
        ),
    )


def _run_fix(
    monkeypatch: pytest.MonkeyPatch,
    health: _FixHealthUseCase,
    fix: _FixUseCase,
    scan: _FixScan,
    argv: list[str],
) -> int:
    monkeypatch.setattr(cli, "load_config", lambda: default_config())
    monkeypatch.setattr(cli, "setup_logging_from_config", lambda _config: None)
    monkeypatch.setattr(cli._LOGGER, "error", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "_build_health_check_use_case", lambda: health)
    monkeypatch.setattr(cli, "_build_fix_use_case", lambda: fix)
    monkeypatch.setattr(cli, "_build_scan_devices_use_case", lambda: scan)
    return cli.main(argv)


def test_fix_unknown_or_unavailable_id_returns_one(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    fix = _FixUseCase()

    result = _run_fix(
        monkeypatch,
        _FixHealthUseCase([_health_report(HealthStatus.OK)]),
        fix,
        _FixScan([]),
        ["fix", "no-existe"],
    )

    assert result == 1
    assert "No hay auto-fix disponible ahora: no-existe" in capsys.readouterr().out
    assert fix.requests == []


def test_fix_start_audio_executes_and_rechecks_health(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    health = _FixHealthUseCase(
        [
            _fix_report("start.audio"),
            _fix_report("start.audio", message="sink por defecto disponible"),
        ]
    )
    fix = _FixUseCase()
    monkeypatch.setattr("builtins.input", lambda _prompt: pytest.fail("input must not be called"))

    result = _run_fix(monkeypatch, health, fix, _FixScan([]), ["fix", "start.audio", "--yes"])
    output = capsys.readouterr().out

    assert result == 0
    assert health.calls == 2
    assert len(fix.requests) == 1
    assert "Verificación:" in output


def test_fix_profile_requires_a_connected_device(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    fix = _FixUseCase()

    result = _run_fix(
        monkeypatch,
        _FixHealthUseCase([_fix_report("profile.a2dp", check_id="audio.profile")]),
        fix,
        _FixScan([_session_device(connected=False)]),
        ["fix", "profile.a2dp", "--yes"],
    )

    assert result == 1
    assert "requiere un dispositivo conectado" in capsys.readouterr().err
    assert fix.requests == []


def test_fix_declining_confirmation_cancels_without_execution(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    fix = _FixUseCase()
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")

    result = _run_fix(
        monkeypatch,
        _FixHealthUseCase([_fix_report("start.audio")]),
        fix,
        _FixScan([]),
        ["fix", "start.audio"],
    )

    assert result == 0
    assert "Cancelado." in capsys.readouterr().out
    assert fix.requests == []


class _LogsUseCase:
    def __init__(self, logs: tuple[ServiceLogs, ...]) -> None:
        self.logs = logs
        self.requests: list[object] = []

    def execute(self, request: object) -> tuple[ServiceLogs, ...]:
        self.requests.append(request)
        return self.logs


def _run_logs(
    monkeypatch: pytest.MonkeyPatch,
    use_case: _LogsUseCase,
    argv: list[str],
) -> int:
    monkeypatch.setattr(cli, "load_config", lambda: default_config())
    monkeypatch.setattr(cli, "setup_logging_from_config", lambda _config: None)
    monkeypatch.setattr(cli, "_build_logs_use_case", lambda: use_case)
    return cli.main(argv)


def test_logs_parser_supports_repeated_services_and_bounded_lines() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(
        ["logs", "--service", "bluez", "--service", "pipewire", "--lines", "7"]
    )

    assert args.service == ["bluez", "pipewire"]
    assert args.lines == 7
    assert not hasattr(args, "yes")
    for invalid in ("0", "201"):
        with pytest.raises(SystemExit):
            parser.parse_args(["logs", "--lines", invalid])


def test_logs_prints_available_and_unavailable_services_without_identifiers(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    use_case = _LogsUseCase(
        (
            ServiceLogs(
                "bluez",
                True,
                ("event 00:11:22:33:44:55 /org/bluez/hci0/dev_00_11_22_33_44_55",),
            ),
            ServiceLogs(
                "wireplumber",
                False,
                error="permission denied for 00:11:22:33:44:55 /org/bluez/hci0",
            ),
        )
    )

    result = _run_logs(monkeypatch, use_case, ["logs", "--service", "bluez", "--lines", "5"])
    output = capsys.readouterr().out

    assert result == 0
    assert "=== bluez ===" in output
    assert "event <redacted> <redacted>" in output
    assert "(no disponible: permission denied for <redacted> <redacted>)" in output
    assert "00:11:22:33:44:55" not in output
    assert "/org/bluez/" not in output


def test_logs_returns_one_when_all_services_are_unavailable(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    use_case = _LogsUseCase(
        (
            ServiceLogs("bluez", False, error="journalctl no disponible"),
            ServiceLogs("pipewire", False, error="servicio no disponible o sin permisos"),
        )
    )

    result = _run_logs(monkeypatch, use_case, ["logs"])
    output = capsys.readouterr().out

    assert result == 1
    assert "=== bluez ===" in output
    assert "=== pipewire ===" in output
    assert "(no disponible: journalctl no disponible)" in output


def _status_device() -> DeviceInfo:
    return DeviceInfo(
        object_path="/org/bluez/hci0/dev_00_11_22_33_44_55",
        address="00:11:22:33:44:55",
        name="Buds",
        alias="Buds",
        icon=DeviceIcon.UNKNOWN,
        address_type=AddressType.UNKNOWN,
        paired=True,
        connected=True,
        trusted=False,
        blocked=False,
        services_resolved=False,
        connection_state=ConnectionState.CONNECTED,
    )


class _StatusScan:
    def __init__(self, devices: list[DeviceInfo] | Exception) -> None:
        self.devices = devices

    def execute(self, _request: object) -> list[DeviceInfo]:
        if isinstance(self.devices, Exception):
            raise self.devices
        return self.devices


class _StatusInfo:
    def __init__(self, aggregate: DeviceAggregate | Exception) -> None:
        self.aggregate = aggregate

    def execute(self, _path: str) -> DeviceAggregate | None:
        if isinstance(self.aggregate, Exception):
            raise self.aggregate
        return self.aggregate


def _status_aggregate() -> DeviceAggregate:
    return DeviceAggregate(
        device=_status_device(),
        battery=None,
        rssi=None,
        codec=CodecInfo(CodecType.SBC, BluetoothProfile.A2DP),
        audio_nodes=(
            BluetoothAudioNode(
                "bluez_output.00_11_22_33_44_55.1", "Audio/Sink", "a2dp-sink", "sbc", ""
            ),
        ),
    )


def _run_status(
    monkeypatch: pytest.MonkeyPatch,
    scan: _StatusScan,
    info: _StatusInfo,
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, str, str]:
    monkeypatch.setattr(cli, "load_config", lambda: default_config())
    monkeypatch.setattr(cli, "setup_logging_from_config", lambda _config: None)
    monkeypatch.setattr(cli._LOGGER, "error", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "_build_scan_devices_use_case", lambda: scan)
    monkeypatch.setattr(cli, "_build_get_device_info_use_case", lambda: info)
    result = cli.main(["status"])
    captured = capsys.readouterr()
    return result, captured.out, captured.err


def test_status_no_paired_devices(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    result, output, _ = _run_status(
        monkeypatch, _StatusScan([]), _StatusInfo(_status_aggregate()), capsys
    )

    assert result == 0
    assert output == "No se encontraron dispositivos emparejados.\n"


def test_status_prints_aggregate_without_identifiers(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    result, output, _ = _run_status(
        monkeypatch, _StatusScan([_status_device()]), _StatusInfo(_status_aggregate()), capsys
    )

    assert result == 0
    assert "Dispositivo: Buds" in output
    assert "Estado: conectado" in output
    assert "Perfil: a2dp" in output
    assert "Códec: sbc (a2dp)" in output
    assert "Sink: bluez_output.<redacted>.1" in output
    assert "00:11:22:33:44:55" not in output
    assert "/org/bluez/" not in output


def test_status_hides_unverified_codec_as_unavailable(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    aggregate = DeviceAggregate(
        device=_status_device(),
        battery=None,
        rssi=None,
        codec=CodecInfo(CodecType.UNKNOWN, BluetoothProfile.UNKNOWN, verified=False),
        audio_nodes=(),
    )
    result, output, _ = _run_status(
        monkeypatch, _StatusScan([_status_device()]), _StatusInfo(aggregate), capsys
    )

    assert result == 0
    assert "Perfil: No disponible" in output
    assert "Códec: No disponible" in output
    assert "unknown" not in output


def test_status_error_propagates(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    result, _, error = _run_status(
        monkeypatch,
        _StatusScan([_status_device()]),
        _StatusInfo(OpenBudsError("status failed")),
        capsys,
    )

    assert result == 1
    assert error == "Error: status failed\n"


class _WatchUseCase:
    def __init__(self, stop: threading.Event, emit: bool = True) -> None:
        self.stop = stop
        self.unsubscribed = False
        self.emit = emit

    def subscribe(self, callback: object) -> object:
        if not self.emit:
            return lambda: setattr(self, "unsubscribed", True)

        def notify() -> None:
            time.sleep(0.05)
            assert callable(callback)
            current = replace(
                _status_device(), connected=True, connection_state=ConnectionState.CONNECTED
            )
            previous = replace(
                _status_device(),
                paired=False,
                connected=False,
                connection_state=ConnectionState.DISCONNECTED,
            )
            callback(DeviceChangeEvent(DeviceChangeKind.UPDATED, current, previous))
            self.stop.set()

        threading.Thread(target=notify, daemon=True).start()

        def unsubscribe() -> None:
            self.unsubscribed = True

        return unsubscribe


def test_watch_prints_changes_and_unsubscribes(capsys: pytest.CaptureFixture[str]) -> None:
    stop = threading.Event()
    use_case = _WatchUseCase(stop)
    context = cli.CliContext(config=default_config(), watch_devices_use_case=use_case)  # type: ignore[arg-type]
    args = cli.build_parser().parse_args(["watch"])

    result = cli._cmd_watch(context, args, stop=stop)
    output = capsys.readouterr().out

    assert result == 0
    assert "[cambio]" in output
    assert "conectado" in output
    assert "(conexión: desconectado → conectado)" in output
    assert use_case.unsubscribed is True
    assert "00:11:22:33:44:55" not in output
    assert "/org/bluez/" not in output


def test_watch_stop_event_terminates_without_events(capsys: pytest.CaptureFixture[str]) -> None:
    stop = threading.Event()
    stop.set()
    use_case = _WatchUseCase(stop, emit=False)
    context = cli.CliContext(config=default_config(), watch_devices_use_case=use_case)  # type: ignore[arg-type]
    args = cli.build_parser().parse_args(["watch"])

    result = cli._cmd_watch(context, args, stop=stop)
    output = capsys.readouterr().out

    assert result == 0
    assert "Observando cambios" in output
    assert "Watch finalizado." in output
    assert use_case.unsubscribed is True


def test_watch_error_propagates(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "load_config", lambda: default_config())
    monkeypatch.setattr(cli, "setup_logging_from_config", lambda _config: None)
    monkeypatch.setattr(cli._LOGGER, "error", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        cli,
        "_build_watch_devices_use_case",
        lambda: (_ for _ in ()).throw(OpenBudsError("watch failed")),
    )

    assert cli.main(["watch"]) == 1
    assert capsys.readouterr().err == "Error: watch failed\n"


class _SessionScan:
    def __init__(self, devices: list[DeviceInfo]) -> None:
        self.devices = devices
        self.requests: list[object] = []

    def execute(self, request: object) -> list[DeviceInfo]:
        self.requests.append(request)
        return self.devices


class _SessionBluetoothAction:
    def __init__(self) -> None:
        self.requests: list[object] = []

    def execute(self, request: object) -> None:
        self.requests.append(request)


class _SessionAudioAction:
    def __init__(self) -> None:
        self.requests: list[object] = []

    def execute(self, request: object) -> str:
        self.requests.append(request)
        return "profile"


def _session_device(name: str = "Buds", connected: bool = True) -> DeviceInfo:
    return replace(
        _status_device(),
        object_path="/org/bluez/hci0/dev_00_11_22_33_44_55",
        name=name,
        alias=name,
        connected=connected,
        connection_state=(ConnectionState.CONNECTED if connected else ConnectionState.DISCONNECTED),
    )


def _run_session_command(
    monkeypatch: pytest.MonkeyPatch,
    scan: _SessionScan,
    connect: _SessionBluetoothAction,
    disconnect: _SessionBluetoothAction,
    audio: _SessionAudioAction,
    argv: list[str],
) -> int:
    monkeypatch.setattr(cli, "load_config", lambda: default_config())
    monkeypatch.setattr(cli, "setup_logging_from_config", lambda _config: None)
    monkeypatch.setattr(cli._LOGGER, "error", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        cli,
        "_build_session_use_cases",
        lambda: (connect, disconnect, audio, scan),
    )
    return cli.main(argv)


def test_connect_resolves_name_case_insensitively_and_confirms(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    scan = _SessionScan([_session_device()])
    connect = _SessionBluetoothAction()

    monkeypatch.setattr("builtins.input", lambda _prompt: "s")
    result = _run_session_command(
        monkeypatch,
        scan,
        connect,
        _SessionBluetoothAction(),
        _SessionAudioAction(),
        ["connect", "bUdS"],
    )
    output = capsys.readouterr().out

    assert result == 0
    assert "Conectado: Buds" in output
    assert "openbuds music para A2DP" in output
    assert connect.requests
    assert "00:11:22:33:44:55" not in output
    assert "/org/bluez/" not in output


def test_connect_yes_skips_input_and_disconnect_reports_success(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    device = _session_device()
    scan = _SessionScan([device])
    connect = _SessionBluetoothAction()
    disconnect = _SessionBluetoothAction()

    monkeypatch.setattr("builtins.input", lambda _prompt: pytest.fail("input must not be called"))
    assert (
        _run_session_command(
            monkeypatch,
            scan,
            connect,
            disconnect,
            _SessionAudioAction(),
            ["connect", "Buds", "--yes"],
        )
        == 0
    )
    assert (
        _run_session_command(
            monkeypatch,
            scan,
            connect,
            disconnect,
            _SessionAudioAction(),
            ["disconnect", "Buds", "-y"],
        )
        == 0
    )
    assert "Desconectado: Buds" in capsys.readouterr().out
    assert disconnect.requests


def test_music_applies_a2dp_and_mic_prints_warning(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    scan = _SessionScan([_session_device()])
    audio = _SessionAudioAction()

    monkeypatch.setattr("builtins.input", lambda _prompt: "s")
    assert (
        _run_session_command(
            monkeypatch,
            scan,
            _SessionBluetoothAction(),
            _SessionBluetoothAction(),
            audio,
            ["music", "buds"],
        )
        == 0
    )
    assert "Perfil A2DP aplicado a Buds" in capsys.readouterr().out
    assert audio.requests[-1].profile is BluetoothProfile.A2DP  # type: ignore[union-attr]

    assert (
        _run_session_command(
            monkeypatch,
            scan,
            _SessionBluetoothAction(),
            _SessionBluetoothAction(),
            audio,
            ["mic", "--yes"],
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "Advertencia: activar el micrófono Bluetooth (HFP)" in output
    assert "Perfil HFP aplicado a Buds" in output
    assert audio.requests[-1].profile is BluetoothProfile.HFP  # type: ignore[union-attr]


def test_declining_confirmation_cancels_without_execution(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    connect = _SessionBluetoothAction()
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")

    result = _run_session_command(
        monkeypatch,
        _SessionScan([_session_device()]),
        connect,
        _SessionBluetoothAction(),
        _SessionAudioAction(),
        ["connect", "Buds"],
    )

    assert result == 0
    assert connect.requests == []
    assert capsys.readouterr().out == "Cancelado.\n"


def test_noninteractive_confirmation_is_an_error(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt: (_ for _ in ()).throw(EOFError))

    result = _run_session_command(
        monkeypatch,
        _SessionScan([_session_device()]),
        _SessionBluetoothAction(),
        _SessionBluetoothAction(),
        _SessionAudioAction(),
        ["connect", "Buds"],
    )

    assert result == 1
    assert "usa --yes en modo no interactivo" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("devices", "argv", "message"),
    [
        ([], ["connect", "Missing", "--yes"], "dispositivo no encontrado"),
        (
            [_session_device("Buds"), _session_device("Buds")],
            ["connect", "Buds", "--yes"],
            "nombre ambiguo",
        ),
        ([_session_device(connected=False)], ["music", "--yes"], "ningún dispositivo conectado"),
    ],
)
def test_session_resolution_errors_return_one(
    devices: list[DeviceInfo],
    argv: list[str],
    message: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run_session_command(
        monkeypatch,
        _SessionScan(devices),
        _SessionBluetoothAction(),
        _SessionBluetoothAction(),
        _SessionAudioAction(),
        argv,
    )

    assert result == 1
    error = capsys.readouterr().err
    assert message in error
    assert "00:11:22:33:44:55" not in error
    assert "/org/bluez/" not in error
