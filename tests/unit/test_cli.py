"""Tests del contrato base de la CLI."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

import openbuds.cli.main as cli
from openbuds import __version__
from openbuds.application.get_device_info import DeviceAggregate
from openbuds.core.config import CONFIG_FILE, default_config
from openbuds.core.errors import ConfigError, OpenBudsError
from openbuds.domain.enums import (
    AddressType,
    BluetoothProfile,
    CodecType,
    ConnectionState,
    DeviceIcon,
)
from openbuds.domain.models import BluetoothAudioNode, CodecInfo, DeviceInfo, SystemInfo


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
        ("health", "Etapa 4"),
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
