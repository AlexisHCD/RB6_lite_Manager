"""Tests for the read-only Health Check flow in the Qt MVP window."""

from __future__ import annotations

import logging
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from time import monotonic

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QEventLoop
from PySide6.QtWidgets import QApplication

from openbuds.domain.enums import CheckSeverity, HealthStatus
from openbuds.domain.models import CheckResult, HealthReport
from openbuds.presentation.qt.main_window import MainWindow
from openbuds.presentation.qt.view_models import DeviceViewModel


@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    """Provide one offscreen application for widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class EmptyScan:
    """Fake paired-device scan that performs no system access."""

    def execute(self, _request: object) -> list[object]:
        return []


class EmptyInfo:
    """Fake aggregate information use case."""

    def execute(self, _path: str) -> None:
        return None


class NoopAction:
    """Fake session action for the MainWindow composition test."""

    def execute(self, _request: object) -> None:
        return None


class FakeHealth:
    """Fake read-only Health Check use case injected into the ViewModel."""

    def __init__(self, report: HealthReport) -> None:
        self.report = report

    def execute(self) -> HealthReport:
        return self.report


class FakeTray:
    """Injected tray lifecycle fake for the MainWindow composition test."""

    def __init__(self) -> None:
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


class FakeDeviceChangeBridge:
    """Injected bridge fake for MainWindow lifecycle coverage."""

    def __init__(self) -> None:
        self.start_calls = 0
        self.close_calls = 0

    def start(self) -> None:
        self.start_calls += 1

    def close(self) -> None:
        self.close_calls += 1


class FailingWatch:
    """Subscription source that simulates unavailable BlueZ observation."""

    def subscribe(self, _callback: object) -> object:
        raise RuntimeError("private subscription detail")


def _report() -> HealthReport:
    return HealthReport(
        overall_status=HealthStatus.OK,
        checks=(
            CheckResult(
                check_id="runtime.read_only",
                label="Lectura segura",
                severity=CheckSeverity.OK,
                message="OK",
            ),
        ),
    )


def _wait_until_idle(view_model: DeviceViewModel, app: QCoreApplication) -> None:
    deadline = monotonic() + 2.0
    while view_model.busy and monotonic() < deadline:
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
    assert view_model.busy is False


def test_diagnostic_handler_opens_dialog_and_renders_injected_report(
    qt_app: QApplication,
) -> None:
    view_model = DeviceViewModel(
        EmptyScan(),  # type: ignore[arg-type]
        EmptyInfo(),  # type: ignore[arg-type]
        NoopAction(),  # type: ignore[arg-type]
        NoopAction(),  # type: ignore[arg-type]
        NoopAction(),  # type: ignore[arg-type]
        FakeHealth(_report()),  # type: ignore[arg-type]
    )
    window = MainWindow(view_model)
    try:
        _wait_until_idle(view_model, qt_app)
        window.diagnostic_button.click()

        assert window._health_dialog is not None
        assert window._health_dialog.isVisible() is True
        assert window._health_dialog.status_label.text() == "Analizando..."
        assert window.diagnostic_button.isEnabled() is False
        _wait_until_idle(view_model, qt_app)
        assert "Estado global: OK" in window._health_dialog.report_text.toPlainText()
        assert "runtime.read_only" in window._health_dialog.report_text.toPlainText()
    finally:
        window.close()


def test_main_window_closes_injected_tray_before_view_model_cleanup(
    qt_app: QApplication,
) -> None:
    view_model = DeviceViewModel(
        EmptyScan(),  # type: ignore[arg-type]
        EmptyInfo(),  # type: ignore[arg-type]
        NoopAction(),  # type: ignore[arg-type]
        NoopAction(),  # type: ignore[arg-type]
        NoopAction(),  # type: ignore[arg-type]
        FakeHealth(_report()),  # type: ignore[arg-type]
    )
    tray = FakeTray()
    window = MainWindow(view_model, tray_controller=tray)  # type: ignore[arg-type]
    try:
        _wait_until_idle(view_model, qt_app)
        window.close()
    finally:
        if not window.isHidden():
            window.close()

    assert tray.close_calls == 1


def test_main_window_starts_and_closes_injected_device_change_bridge(
    qt_app: QApplication,
) -> None:
    view_model = DeviceViewModel(
        EmptyScan(),  # type: ignore[arg-type]
        EmptyInfo(),  # type: ignore[arg-type]
        NoopAction(),  # type: ignore[arg-type]
        NoopAction(),  # type: ignore[arg-type]
        NoopAction(),  # type: ignore[arg-type]
        FakeHealth(_report()),  # type: ignore[arg-type]
    )
    bridge = FakeDeviceChangeBridge()
    window = MainWindow(view_model, device_change_bridge=bridge)  # type: ignore[arg-type]
    try:
        assert bridge.start_calls == 1
        window.close()
        window.close()
    finally:
        if not window.isHidden():
            window.close()

    assert bridge.close_calls == 1


def test_main_window_survives_device_change_subscription_failure(
    qt_app: QApplication,
    caplog: pytest.LogCaptureFixture,
) -> None:
    view_model = DeviceViewModel(
        EmptyScan(),  # type: ignore[arg-type]
        EmptyInfo(),  # type: ignore[arg-type]
        NoopAction(),  # type: ignore[arg-type]
        NoopAction(),  # type: ignore[arg-type]
        NoopAction(),  # type: ignore[arg-type]
        FakeHealth(_report()),  # type: ignore[arg-type]
    )
    with caplog.at_level(logging.WARNING):
        window = MainWindow(
            view_model,
            watch_devices=FailingWatch(),  # type: ignore[arg-type]
            notifier=object(),  # type: ignore[arg-type]
        )
    try:
        bridge = window.device_change_bridge
        assert bridge is not None
        bootstrap_thread = bridge._bootstrap_thread
        assert bootstrap_thread is not None
        bootstrap_thread.join(timeout=1.0)
        assert bootstrap_thread.is_alive() is False
        assert window.isEnabled() is True
        assert "Las notificaciones automáticas de cambios no están disponibles." in caplog.text
        assert "private subscription detail" not in caplog.text
    finally:
        window.close()
