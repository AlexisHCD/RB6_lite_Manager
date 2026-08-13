"""Tests for the read-only Health Check flow in the Qt MVP window."""

from __future__ import annotations

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
