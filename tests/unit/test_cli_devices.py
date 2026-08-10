"""Pruebas unitarias del comando ``openbuds devices``."""

from __future__ import annotations

import re

import pytest

import openbuds.cli.main as cli
from openbuds.application.scan_devices import ScanDevicesRequest
from openbuds.core.config import default_config
from openbuds.core.errors import BluetoothError
from openbuds.domain.enums import AddressType, ConnectionState, DeviceIcon
from openbuds.domain.models import DeviceInfo


def _device(
    *,
    name: str = "Name",
    alias: str = "Alias",
    paired: bool = True,
    state: ConnectionState = ConnectionState.CONNECTED,
    adapter_path: str = "/org/bluez/hci0",
) -> DeviceInfo:
    return DeviceInfo(
        object_path="/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF",
        address="AA:BB:CC:DD:EE:FF",
        name=name,
        alias=alias,
        icon=DeviceIcon.UNKNOWN,
        address_type=AddressType.PUBLIC,
        paired=paired,
        connected=state is ConnectionState.CONNECTED,
        trusted=False,
        blocked=False,
        services_resolved=False,
        adapter_path=adapter_path,
        connection_state=state,
    )


class FakeUseCase:
    def __init__(self, devices: list[DeviceInfo] | Exception) -> None:
        self.devices = devices
        self.requests: list[object] = []

    def execute(self, request: object) -> list[DeviceInfo]:
        self.requests.append(request)
        if isinstance(self.devices, Exception):
            raise self.devices
        return self.devices


def _run(
    monkeypatch: pytest.MonkeyPatch,
    use_case: FakeUseCase,
    argv: list[str],
    bootstrap_calls: list[str] | None = None,
) -> int:
    calls = bootstrap_calls if bootstrap_calls is not None else []
    monkeypatch.setattr(cli, "load_config", lambda: calls.append("load") or default_config())
    monkeypatch.setattr(cli, "setup_logging_from_config", lambda _config: calls.append("logging"))
    monkeypatch.setattr(cli, "_build_scan_devices_use_case", lambda: use_case)
    return cli.main(argv)


def test_parser_normalizes_adapter_and_options() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["devices", "-p", "-a", "hci2"])
    full_path = parser.parse_args(["devices", "--adapter", "/org/bluez/hci3"])

    assert args.paired_only is True
    assert args.adapter == "/org/bluez/hci2"
    assert full_path.adapter == "/org/bluez/hci3"


def test_invalid_adapter_fails_before_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "load_config", pytest.fail)

    with pytest.raises(SystemExit) as raised:
        cli.main(["devices", "--adapter", "hci0/extra"])

    assert raised.value.code == 2


def test_bootstraps_once_and_sends_exact_request(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    use_case = FakeUseCase([_device()])
    calls: list[str] = []

    assert _run(monkeypatch, use_case, ["devices", "-p", "-a", "hci1"], calls) == 0

    request = use_case.requests == [
        ScanDevicesRequest(adapter_path="/org/bluez/hci1", include_paired_only=True)
    ]
    assert request
    assert calls == ["load", "logging"]
    assert capsys.readouterr().out.startswith("NOMBRE\tCONEXIÓN\tEMPAREJAMIENTO\tADAPTADOR\n")


def test_output_uses_alias_precedence_and_tokens(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    use_case = FakeUseCase(
        [
            _device(alias="Preferred", name="Name"),
            _device(alias="", name="Name", paired=False, state=ConnectionState.DISCONNECTED),
        ]
    )

    assert _run(monkeypatch, use_case, ["devices"]) == 0
    lines = capsys.readouterr().out.splitlines()

    assert lines[0] == "NOMBRE\tCONEXIÓN\tEMPAREJAMIENTO\tADAPTADOR"
    assert lines[1] == "Preferred\tconectado\temparejado\thci0"
    assert lines[2] == "Name\tdesconectado\tno emparejado\thci0"


def test_sanitizes_and_truncates_dynamic_fields(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    use_case = FakeUseCase(
        [_device(alias="A\tB\nC\rD\x1bE\x00" + "x" * 100, adapter_path="/org/bluez/invalid")]
    )

    assert _run(monkeypatch, use_case, ["devices"]) == 0
    row = capsys.readouterr().out.splitlines()[1]

    assert row.split("\t") == ["A?B?C?D?E?" + "x" * 70, "conectado", "emparejado", "desconocido"]
    assert len(row.split("\t")[0]) == 80


def test_fallback_and_privacy(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    use_case = FakeUseCase([_device(alias="", name="")])

    assert _run(monkeypatch, use_case, ["devices"]) == 0
    output = capsys.readouterr().out

    assert "Dispositivo sin nombre" in output
    assert "AA:BB:CC:DD:EE:FF" not in output
    assert "dev_AA_BB_CC_DD_EE_FF" not in output


def test_empty_output_is_exact(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _run(monkeypatch, FakeUseCase([]), ["devices"]) == 0
    assert capsys.readouterr().out == "No se encontraron dispositivos Bluetooth.\n"


def test_bluetooth_error_is_reported(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _run(monkeypatch, FakeUseCase(BluetoothError("bus unavailable")), ["devices"]) == 1
    assert capsys.readouterr().err == "Error: bus unavailable\n"


def test_unexpected_error_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(RuntimeError, match="bug"):
        _run(monkeypatch, FakeUseCase(RuntimeError("bug")), ["devices"])


def test_output_contains_no_mac_or_object_path(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(monkeypatch, FakeUseCase([_device()]), ["devices"]) == 0
    output = capsys.readouterr().out
    assert re.search(r"[0-9A-F]{2}(?::[0-9A-F]{2}){5}", output) is None
    assert "dev_" not in output
