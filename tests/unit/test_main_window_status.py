"""Behavioral tests for the main-window status bar."""

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
    CodecType,
    ConnectionState,
    DeviceIcon,
)
from openbuds.domain.models import (
    BatteryLevel,
    BluetoothAudioNode,
    CodecInfo,
    DeviceInfo,
    RSSIReading,
)
from openbuds.presentation.qt.main_window import MainWindow
from openbuds.presentation.qt.view_models import DeviceViewModel


@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    """Provide one offscreen application for widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _device() -> DeviceInfo:
    return DeviceInfo(
        object_path="/org/bluez/hci0/dev_00_11_22_33_44_55",
        address="00:11:22:33:44:55",
        name="Redmi Buds 6 Lite",
        alias="Buds",
        icon=DeviceIcon.UNKNOWN,
        address_type=AddressType.UNKNOWN,
        paired=True,
        connected=True,
        trusted=False,
        blocked=False,
        services_resolved=True,
        connection_state=ConnectionState.CONNECTED,
    )


def _aggregate(device: DeviceInfo) -> DeviceAggregate:
    return DeviceAggregate(
        device=device,
        battery=BatteryLevel(80),
        rssi=RSSIReading(-42, datetime.now(UTC)),
        codec=CodecInfo(CodecType.SBC, BluetoothProfile.A2DP),
        audio_nodes=(
            BluetoothAudioNode("bluez_output.dynamic", "Audio/Sink", None, None, None),
            BluetoothAudioNode("bluez_input.dynamic", "Audio/Source", None, None, None),
        ),
    )


class FakeScan:
    """Fake paired-device scan with an optional gate or error."""

    def __init__(self, device: DeviceInfo, *, gate: Event | None = None) -> None:
        self.device = device
        self.gate = gate
        self.error: Exception | None = None

    def execute(self, _request: ScanDevicesRequest) -> list[DeviceInfo]:
        if self.gate is not None:
            self.gate.wait()
        if self.error is not None:
            raise self.error
        return [self.device]


class FakeInfo:
    """Fake aggregate information use case."""

    def __init__(self, aggregate: DeviceAggregate) -> None:
        self.aggregate = aggregate

    def execute(self, _path: str) -> DeviceAggregate:
        return self.aggregate


class FakeAction:
    """Fake session action with an optional completion gate."""

    def __init__(self, gate: Event | None = None) -> None:
        self.gate = gate

    def execute(self, _request: object) -> None:
        if self.gate is not None:
            self.gate.wait()


def _view_model(
    scan: FakeScan,
    info: FakeInfo,
    action: FakeAction | None = None,
) -> DeviceViewModel:
    noop = FakeAction()
    return DeviceViewModel(
        scan,  # type: ignore[arg-type]
        info,  # type: ignore[arg-type]
        action if action is not None else noop,  # type: ignore[arg-type]
        noop,  # type: ignore[arg-type]
        noop,  # type: ignore[arg-type]
    )


def _wait_until_idle(view_model: DeviceViewModel, app: QApplication) -> None:
    """Wait for queued completion while keeping a bounded event-loop timeout."""
    deadline = monotonic() + 2.0
    while view_model.busy and monotonic() < deadline:
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
    assert view_model.busy is False


def test_periodic_refresh_keeps_ready_status_while_worker_is_busy(
    qt_app: QApplication,
) -> None:
    """The timer refresh is background work and must not announce each cycle."""
    device = _device()
    scan = FakeScan(device)
    view_model = _view_model(scan, FakeInfo(_aggregate(device)))
    window = MainWindow(view_model)
    try:
        _wait_until_idle(view_model, qt_app)
        window._refresh_timer.stop()

        gate = Event()
        scan.gate = gate
        window._refresh_timer.timeout.emit()

        assert view_model.busy is True
        assert window.status_label.text() == "Listo"
        assert window.connect_button.isEnabled() is False
        assert window.disconnect_button.isEnabled() is True
        assert window.music_button.isEnabled() is True
        assert window.mic_button.isEnabled() is True
        assert window.refresh_button.isEnabled() is True
        assert window.diagnostic_button.isEnabled() is True

        QTimer.singleShot(0, gate.set)
        _wait_until_idle(view_model, qt_app)
        assert window.status_label.text() == "Listo"
    finally:
        gate.set()
        window.close()


def test_explicit_action_still_shows_progress_status(qt_app: QApplication) -> None:
    """User-requested session actions retain their progress feedback."""
    device = _device()
    action_gate = Event()
    view_model = _view_model(
        FakeScan(device),
        FakeInfo(_aggregate(device)),
        FakeAction(action_gate),
    )
    window = MainWindow(view_model)
    try:
        _wait_until_idle(view_model, qt_app)
        view_model.connect_device()
        window._refresh_timer.stop()

        assert view_model.busy is True
        assert window.status_label.text() == "Actualizando..."
        assert window.connect_button.isEnabled() is False
        assert window.disconnect_button.isEnabled() is False
        assert window.music_button.isEnabled() is False
        assert window.mic_button.isEnabled() is False
        assert window.refresh_button.isEnabled() is False
        assert window.diagnostic_button.isEnabled() is False
        window._refresh_timer.timeout.emit()
        view_model.state_changed.emit()
        assert window.status_label.text() == "Actualizando..."
        assert window.connect_button.isEnabled() is False
        assert window.disconnect_button.isEnabled() is False
        assert window.music_button.isEnabled() is False
        assert window.mic_button.isEnabled() is False
        assert window.refresh_button.isEnabled() is False
        assert window.diagnostic_button.isEnabled() is False

        QTimer.singleShot(0, action_gate.set)
        _wait_until_idle(view_model, qt_app)
        assert window.status_label.text() == "Listo"
        assert window.disconnect_button.isEnabled() is True
        assert window.music_button.isEnabled() is True
        assert window.mic_button.isEnabled() is True
    finally:
        action_gate.set()
        window.close()


def test_periodic_refresh_error_remains_visible_and_sanitized(
    qt_app: QApplication,
) -> None:
    """Background refresh failures remain visible without dynamic identifiers."""
    device = _device()
    scan = FakeScan(device)
    view_model = _view_model(scan, FakeInfo(_aggregate(device)))
    window = MainWindow(view_model)
    try:
        _wait_until_idle(view_model, qt_app)
        window._refresh_timer.stop()
        scan.error = OpenBudsError(
            "falló /org/bluez/hci0/dev_00_11_22_33_44_55 (00:11:22:33:44:55)"
        )

        window._refresh_timer.timeout.emit()
        _wait_until_idle(view_model, qt_app)

        status = window.status_label.text()
        assert status.startswith("Error: ")
        assert "00:11:22:33:44:55" not in status
        assert "/org/bluez/" not in status
    finally:
        window.close()
