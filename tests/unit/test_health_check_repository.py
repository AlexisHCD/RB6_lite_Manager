"""Unit tests for the read-only Health Check repository."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from openbuds.core.errors import BluetoothError
from openbuds.domain.enums import (
    AddressType,
    BluetoothProfile,
    CheckSeverity,
    CodecType,
    ConnectionState,
    DeviceIcon,
    EvidenceKind,
    HealthStatus,
)
from openbuds.domain.models import (
    BatteryLevel,
    BluetoothAudioNode,
    CheckResult,
    CodecInfo,
    DeviceInfo,
    HealthReport,
    ServiceLogs,
    SystemInfo,
)
from openbuds.infrastructure.diagnostics.health_check_repository import HealthCheckRepository

ADDRESS = "00:11:22:33:44:55"
DEVICE_PATH = "/org/bluez/hci0/dev_00_11_22_33_44_55"
_DEFAULT_BATTERY = BatteryLevel(82)
_DEFAULT_CODEC = CodecInfo(CodecType.SBC, BluetoothProfile.A2DP)


def _system_info(**changes: object) -> SystemInfo:
    info = SystemInfo(
        os_id="ubuntu",
        os_version="24.04",
        kernel_version="6.8.0",
        bluez_version="5.72",
        pipewire_version="1.0.5",
        wireplumber_version="0.4.17",
        wireplumber_config_style="lua-0.4",
        dbus_version="systemd 255",
        has_bluetooth_adapter=True,
        system_bus_available=True,
        user_config_writable=True,
        is_supported=True,
    )
    return replace(info, **changes)


def _device(*, paired: bool = True, connected: bool = True) -> DeviceInfo:
    return DeviceInfo(
        object_path=DEVICE_PATH,
        address=ADDRESS,
        name="Fictitious Buds",
        alias="Fictitious Buds",
        icon=DeviceIcon.UNKNOWN,
        address_type=AddressType.UNKNOWN,
        paired=paired,
        connected=connected,
        trusted=False,
        blocked=False,
        services_resolved=False,
        adapter_path="/org/bluez/hci0",
        connection_state=(ConnectionState.CONNECTED if connected else ConnectionState.DISCONNECTED),
    )


class FakeBluetoothRepository:
    """Minimal read-only BlueZ fake for Health Check tests."""

    def __init__(
        self,
        devices: list[DeviceInfo] | Exception,
        battery: BatteryLevel | None = _DEFAULT_BATTERY,
    ) -> None:
        self.devices = devices
        self.battery = battery

    def list_devices(self, adapter_path: str | None = None) -> list[DeviceInfo]:
        del adapter_path
        if isinstance(self.devices, Exception):
            raise self.devices
        return self.devices

    def get_battery(self, device_path: str) -> BatteryLevel | None:
        assert device_path == DEVICE_PATH
        return self.battery


class FakeAudioRepository:
    """Minimal read-only PipeWire fake for Health Check tests."""

    def __init__(
        self,
        codec: CodecInfo | Exception | None = _DEFAULT_CODEC,
        nodes: list[BluetoothAudioNode] | Exception | None = None,
        sink: str | Exception | None = "alsa_output.pci-0000_00_1f.3.analog-stereo",
    ) -> None:
        self.codec = codec
        self.nodes = [] if nodes is None else nodes
        self.sink = sink

    def get_active_codec(self, device_address: str) -> CodecInfo | None:
        assert device_address == ADDRESS
        if isinstance(self.codec, Exception):
            raise self.codec
        return self.codec

    def list_device_audio_nodes(self, device_address: str) -> list[BluetoothAudioNode]:
        assert device_address == ADDRESS
        if isinstance(self.nodes, Exception):
            raise self.nodes
        return self.nodes

    def get_default_audio_sink(self) -> str | None:
        if isinstance(self.sink, Exception):
            raise self.sink
        return self.sink


class FakeLogReader:
    """Minimal journal reader fake for repository delegation tests."""

    def __init__(self, results: dict[str, tuple[bool, str, str]]) -> None:
        self.results = results
        self.calls: list[tuple[str, int]] = []

    def read(self, service: str, lines: int) -> tuple[bool, str, str]:
        self.calls.append((service, lines))
        return self.results[service]


def _repository(
    bluetooth: FakeBluetoothRepository | None = None,
    audio: FakeAudioRepository | None = None,
    *,
    info: SystemInfo | None = None,
    detect: object | None = None,
    runtime_ready: object | None = None,
    log_reader: object | None = None,
) -> HealthCheckRepository:
    detector = detect if detect is not None else (lambda: info or _system_info())
    runtime = runtime_ready if runtime_ready is not None else (lambda: True)
    return HealthCheckRepository(
        bluetooth or FakeBluetoothRepository([_device()]),  # type: ignore[arg-type]
        audio or FakeAudioRepository(),  # type: ignore[arg-type]
        detect=detector,  # type: ignore[arg-type]
        runtime_ready=runtime,  # type: ignore[arg-type]
        log_reader=log_reader,  # type: ignore[arg-type]
    )


def _checks(report: HealthReport) -> dict[str, CheckResult]:
    return {check.check_id: check for check in report.checks}


def test_all_ok_is_observed_and_has_no_recommendations() -> None:
    report = _repository().run_health_check()

    assert report.overall_status is HealthStatus.OK
    assert report.recommendations == ()
    assert all(check.evidence is EvidenceKind.OBSERVED for check in report.checks)
    assert [check.check_id for check in report.checks] == [
        "system.os",
        "system.bluez",
        "system.pipewire",
        "system.wireplumber",
        "system.dbus",
        "runtime.gio",
        "hardware.adapter",
        "device.paired",
        "device.connected",
        "audio.profile",
        "audio.codec",
        "audio.sink_default",
        "audio.mic",
        "battery.aggregate",
    ]


def test_hfp_and_bluetooth_source_warn_and_recommend_a2dp() -> None:
    audio = FakeAudioRepository(
        codec=CodecInfo(CodecType.MSBC, BluetoothProfile.HFP),
        nodes=[BluetoothAudioNode("bluez_input.fake", "Audio/Source", "hfp", "msbc", None)],
    )

    report = _repository(audio=audio).run_health_check()
    checks = _checks(report)

    assert report.overall_status is HealthStatus.WARNING
    assert checks["audio.profile"].severity is CheckSeverity.WARNING
    assert checks["audio.profile"].evidence is EvidenceKind.OBSERVED
    assert checks["audio.mic"].severity is CheckSeverity.WARNING
    assert checks["audio.mic"].evidence is EvidenceKind.OBSERVED
    assert "openbuds music" in report.recommendations[0]


def test_missing_adapter_warns_but_runtime_failure_is_error() -> None:
    adapter_missing = _repository(info=_system_info(has_bluetooth_adapter=False)).run_health_check()
    runtime_missing = _repository(runtime_ready=lambda: False).run_health_check()

    assert adapter_missing.overall_status is HealthStatus.WARNING
    assert not any(check.severity is CheckSeverity.ERROR for check in adapter_missing.checks)
    assert adapter_missing.recommendations[-1].startswith("Verifica que el Bluetooth")
    assert runtime_missing.overall_status is HealthStatus.ERROR
    assert _checks(runtime_missing)["runtime.gio"].evidence is EvidenceKind.NOT_AVAILABLE


def test_detector_failure_does_not_abort_device_checks() -> None:
    def detect() -> SystemInfo:
        raise RuntimeError("detector failure")

    report = _repository(detect=detect).run_health_check()
    checks = _checks(report)

    assert checks["system.os"].severity is CheckSeverity.ERROR
    assert checks["system.os"].evidence is EvidenceKind.NOT_AVAILABLE
    assert "device.paired" in checks
    assert "audio.sink_default" in checks


def test_bluetooth_error_isolated_to_device_checks() -> None:
    report = _repository(
        bluetooth=FakeBluetoothRepository(BluetoothError("bus unavailable"))
    ).run_health_check()
    checks = _checks(report)

    assert report.overall_status is HealthStatus.WARNING
    for check_id in ("device.paired", "device.connected"):
        assert checks[check_id].severity is CheckSeverity.WARNING
        assert checks[check_id].evidence is EvidenceKind.NOT_AVAILABLE


def test_no_devices_is_valid_ok_report_with_unavailable_device_data() -> None:
    report = _repository(bluetooth=FakeBluetoothRepository([])).run_health_check()
    checks = _checks(report)

    assert report.overall_status is HealthStatus.OK
    assert checks["device.paired"].severity is CheckSeverity.INFO
    assert checks["device.paired"].evidence is EvidenceKind.NOT_AVAILABLE
    assert checks["device.connected"].evidence is EvidenceKind.NOT_AVAILABLE
    assert checks["audio.profile"].evidence is EvidenceKind.NOT_AVAILABLE


def test_default_sink_is_optional_and_redacts_identifiers() -> None:
    audio = FakeAudioRepository(
        sink="bluez_output.00:11:22:33:44:55.1",
    )
    report = _repository(audio=audio).run_health_check()
    sink_check = _checks(report)["audio.sink_default"]

    assert sink_check.severity is CheckSeverity.OK
    assert sink_check.evidence is EvidenceKind.OBSERVED
    assert ADDRESS not in sink_check.detail
    assert "/org/bluez/" not in sink_check.detail

    no_sink = _repository(audio=FakeAudioRepository(sink=None)).run_health_check()
    assert _checks(no_sink)["audio.sink_default"].evidence is EvidenceKind.NOT_AVAILABLE


def test_read_logs_delegates_supported_services_and_skips_unknown() -> None:
    reader = FakeLogReader(
        {
            "bluez": (True, "bluez line 1\nbluez line 2", ""),
            "wireplumber": (False, "", "sin permisos"),
        }
    )
    repository = _repository(log_reader=reader)

    logs = repository.read_logs(("bluez", "unsupported", "wireplumber"), lines=7)

    assert logs == (
        ServiceLogs("bluez", True, ("bluez line 1", "bluez line 2")),
        ServiceLogs("wireplumber", False, (), "sin permisos"),
    )
    assert reader.calls == [("bluez", 7), ("wireplumber", 7)]


def test_generated_at_is_utc_iso_and_all_failures_are_unknown() -> None:
    def detect() -> SystemInfo:
        raise RuntimeError("detector failure")

    def runtime() -> bool:
        raise RuntimeError("runtime failure")

    failing_audio = FakeAudioRepository(
        codec=RuntimeError("codec failure"),
        nodes=RuntimeError("nodes failure"),
        sink=RuntimeError("sink failure"),
    )
    report = _repository(
        bluetooth=FakeBluetoothRepository(RuntimeError("bluez failure")),
        audio=failing_audio,
        detect=detect,
        runtime_ready=runtime,
    ).run_health_check()

    generated = datetime.fromisoformat(report.generated_at)
    assert generated.tzinfo is UTC
    assert report.overall_status is HealthStatus.UNKNOWN


def test_benchmark_remains_unimplemented() -> None:
    repository = _repository()

    with pytest.raises(NotImplementedError):
        repository.run_benchmark(ADDRESS)
