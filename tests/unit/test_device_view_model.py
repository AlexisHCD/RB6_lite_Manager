"""Unit tests for the Qt device ViewModel and its worker boundary."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import UTC, datetime
from threading import Event
from time import monotonic

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from openbuds.application.get_device_info import DeviceAggregate
from openbuds.application.scan_devices import ScanDevicesRequest
from openbuds.core.errors import OpenBudsError
from openbuds.domain.enums import (
    AddressType,
    BluetoothProfile,
    CheckSeverity,
    CodecType,
    ConnectionState,
    DeviceIcon,
    HealthStatus,
)
from openbuds.domain.models import (
    BatteryLevel,
    BluetoothAudioNode,
    CheckResult,
    CodecInfo,
    DeviceInfo,
    HealthReport,
    RSSIReading,
)
from openbuds.presentation.qt.view_models import DeviceViewModel


@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    """Provide one event loop for the QObject tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _device(*, connected: bool = True) -> DeviceInfo:
    return DeviceInfo(
        object_path="/org/bluez/hci0/dev_00_11_22_33_44_55",
        address="00:11:22:33:44:55",
        name="Redmi Buds 6 Lite",
        alias="Buds",
        icon=DeviceIcon.UNKNOWN,
        address_type=AddressType.UNKNOWN,
        paired=True,
        connected=connected,
        trusted=False,
        blocked=False,
        services_resolved=True,
        connection_state=(ConnectionState.CONNECTED if connected else ConnectionState.DISCONNECTED),
    )


def _aggregate(device: DeviceInfo | None = None) -> DeviceAggregate:
    return DeviceAggregate(
        device=device if device is not None else _device(),
        battery=BatteryLevel(80),
        rssi=RSSIReading(-42, datetime.now(UTC)),
        codec=CodecInfo(CodecType.SBC, BluetoothProfile.A2DP),
        audio_nodes=(
            BluetoothAudioNode("bluez_output.00:11:22:33:44:55.1", "Audio/Sink", None, None, None),
            BluetoothAudioNode("bluez_input.00:11:22:33:44:55.1", "Audio/Source", None, None, None),
        ),
    )


class FakeScan:
    """Fake paired-device scan use case."""

    def __init__(
        self,
        devices: list[DeviceInfo] | None = None,
        *,
        error: Exception | None = None,
        gate: Event | None = None,
    ) -> None:
        self.devices = devices if devices is not None else []
        self.error = error
        self.gate = gate
        self.requests: list[ScanDevicesRequest] = []

    def execute(self, request: ScanDevicesRequest) -> list[DeviceInfo]:
        self.requests.append(request)
        if self.gate is not None:
            self.gate.wait()
        if self.error is not None:
            raise self.error
        return self.devices


class FakeInfo:
    """Fake aggregate information use case."""

    def __init__(self, aggregate: DeviceAggregate | None) -> None:
        self.aggregate = aggregate
        self.paths: list[str] = []

    def execute(self, path: str) -> DeviceAggregate | None:
        self.paths.append(path)
        return self.aggregate


class FakeAction:
    """Fake session use case that records its request."""

    def __init__(self, result: object = None, gate: Event | None = None) -> None:
        self.result = result
        self.gate = gate
        self.requests: list[object] = []

    def execute(self, request: object) -> object:
        self.requests.append(request)
        if self.gate is not None:
            self.gate.wait()
        return self.result


class FakeHealth:
    """Fake read-only Health Check use case."""

    def __init__(self, result: HealthReport | Exception, gate: Event | None = None) -> None:
        self.result = result
        self.gate = gate
        self.calls = 0

    def execute(self) -> HealthReport:
        self.calls += 1
        if self.gate is not None:
            self.gate.wait()
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _view_model(
    scan: FakeScan,
    info: FakeInfo,
    connect: FakeAction | None = None,
    disconnect: FakeAction | None = None,
    profile: FakeAction | None = None,
    health: FakeHealth | None = None,
) -> DeviceViewModel:
    return DeviceViewModel(
        scan,  # type: ignore[arg-type]
        info,  # type: ignore[arg-type]
        connect if connect is not None else FakeAction(),  # type: ignore[arg-type]
        disconnect if disconnect is not None else FakeAction(),  # type: ignore[arg-type]
        profile if profile is not None else FakeAction(),  # type: ignore[arg-type]
        health,  # type: ignore[arg-type]
    )


def _health_report() -> HealthReport:
    return HealthReport(
        overall_status=HealthStatus.OK,
        checks=(
            CheckResult(
                check_id="runtime.read_only",
                label="Lectura disponible",
                severity=CheckSeverity.OK,
                message="OK",
            ),
        ),
    )


def _wait_until_idle(view_model: DeviceViewModel, app: QApplication) -> None:
    """Wait for queued completion while keeping a bounded event-loop timeout."""
    deadline = monotonic() + 2.0
    while view_model.busy and monotonic() < deadline:
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
    assert view_model.busy is False


def test_refresh_without_devices_keeps_stable_empty_state(qt_app: QApplication) -> None:
    view_model = _view_model(FakeScan(), FakeInfo(None))
    try:
        view_model.refresh()
        _wait_until_idle(view_model, qt_app)

        assert view_model.device_name == "Sin dispositivos emparejados"
        assert view_model.connection == "No disponible"
        assert view_model.battery == "No disponible"
        assert view_model.sink == "No disponible"
        assert view_model.error == ""
    finally:
        view_model.close()


def test_refresh_populates_aggregate_fields(qt_app: QApplication) -> None:
    device = _device()
    scan = FakeScan([device])
    info = FakeInfo(_aggregate(device))
    view_model = _view_model(scan, info)
    try:
        view_model.refresh()
        _wait_until_idle(view_model, qt_app)

        assert view_model.device_name == "Buds"
        assert view_model.connection == "conectado"
        assert view_model.battery == "80%"
        assert view_model.rssi == "-42 dBm"
        assert view_model.profile == "a2dp"
        assert view_model.codec == "sbc (a2dp)"
        assert view_model.sink == "Disponible"
        assert view_model.source == "Disponible"
        assert info.paths == [device.object_path]
    finally:
        view_model.close()


def test_busy_is_true_until_a_slow_refresh_finishes(qt_app: QApplication) -> None:
    gate = Event()
    view_model = _view_model(FakeScan([_device()], gate=gate), FakeInfo(_aggregate()))
    try:
        view_model.refresh()
        assert view_model.busy is True
        QTimer.singleShot(0, gate.set)
        _wait_until_idle(view_model, qt_app)
        assert view_model.busy is False
    finally:
        view_model.close()


def test_connect_uses_path_and_refreshes(qt_app: QApplication) -> None:
    device = _device()
    scan = FakeScan([device])
    gate = Event()
    connect = FakeAction(gate=gate)
    view_model = _view_model(scan, FakeInfo(_aggregate(device)), connect=connect)
    try:
        view_model.refresh()
        _wait_until_idle(view_model, qt_app)
        initial_scan_count = len(scan.requests)

        view_model.connect_device()
        assert view_model.busy is True
        QTimer.singleShot(0, gate.set)
        _wait_until_idle(view_model, qt_app)

        assert len(connect.requests) == 1
        assert connect.requests[0].device_path == device.object_path  # type: ignore[attr-defined]
        assert len(scan.requests) == initial_scan_count + 1
    finally:
        view_model.close()


def test_mic_warns_and_uses_hfp(qt_app: QApplication) -> None:
    device = _device()
    profile = FakeAction("headset-head-unit-msbc")
    view_model = _view_model(FakeScan([device]), FakeInfo(_aggregate(device)), profile=profile)
    warnings: list[str] = []
    view_model.warning.connect(warnings.append)
    try:
        view_model.refresh()
        _wait_until_idle(view_model, qt_app)

        view_model.mic()
        assert warnings == [
            "Activar el micrófono Bluetooth (HFP) puede reducir la calidad de reproducción."
        ]
        _wait_until_idle(view_model, qt_app)

        assert profile.requests[-1].profile is BluetoothProfile.HFP  # type: ignore[attr-defined]
        assert profile.requests[-1].device_address == device.address  # type: ignore[attr-defined]
    finally:
        view_model.close()


def test_worker_error_is_safe(qt_app: QApplication) -> None:
    message = "failed 00:11:22:33:44:55 /org/bluez/hci0/dev_00_11_22_33_44_55"
    view_model = _view_model(
        FakeScan(error=OpenBudsError(message)),
        FakeInfo(None),
    )
    try:
        view_model.refresh()
        _wait_until_idle(view_model, qt_app)

        assert "failed" in view_model.error
        assert "00:11:22:33:44:55" not in view_model.error
        assert "/org/bluez/" not in view_model.error
    finally:
        view_model.close()


def test_health_check_runs_async_emits_report_and_returns_to_idle(
    qt_app: QApplication,
) -> None:
    gate = Event()
    health = FakeHealth(_health_report(), gate=gate)
    view_model = _view_model(FakeScan(), FakeInfo(None), health=health)
    reports: list[HealthReport] = []
    view_model.health_report.connect(reports.append)
    try:
        view_model.run_health_check()
        assert view_model.busy is True
        deadline = monotonic() + 2.0
        while health.calls == 0 and monotonic() < deadline:
            qt_app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        assert health.calls == 1
        view_model.run_health_check()
        assert health.calls == 1

        QTimer.singleShot(0, gate.set)
        _wait_until_idle(view_model, qt_app)

        assert reports == [_health_report()]
        assert view_model.busy is False
    finally:
        gate.set()
        view_model.close()


def test_health_check_error_is_safe_and_close_is_idempotent(qt_app: QApplication) -> None:
    message = "health failed 00:11:22:33:44:55 /org/bluez/hci0/dev_00_11_22_33_44_55"
    health = FakeHealth(OpenBudsError(message))
    view_model = _view_model(FakeScan(), FakeInfo(None), health=health)
    errors: list[str] = []
    view_model.health_error.connect(errors.append)
    try:
        view_model.run_health_check()
        _wait_until_idle(view_model, qt_app)

        assert errors
        assert "health failed" in errors[0]
        assert "00:11:22:33:44:55" not in errors[0]
        assert "/org/bluez/" not in errors[0]
        assert "00:11:22:33:44:55" not in view_model.error
        assert "/org/bluez/" not in view_model.error
        view_model.close()
    finally:
        view_model.close()
