"""Unit tests for the optional Qt system tray adapter."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QWidget

from openbuds.presentation.qt.tray_controller import TrayController


class FakeSignal:
    """Minimal signal fake for the tray activation callback."""

    def __init__(self) -> None:
        self._slots = []

    def connect(self, slot) -> None:  # type: ignore[no-untyped-def]
        self._slots.append(slot)

    def emit(self, value) -> None:  # type: ignore[no-untyped-def]
        for slot in self._slots:
            slot(value)


class FakeTray:
    """Record the visible state and menu assigned by the controller."""

    def __init__(self) -> None:
        self.activated = FakeSignal()
        self.context_menu = None
        self.tooltip = ""
        self.show_calls = 0
        self.hide_calls = 0
        self.visible = False
        self.raise_on_detach = False
        self.raise_on_hide = False

    def setContextMenu(self, menu) -> None:  # noqa: N802  # type: ignore[no-untyped-def]
        if menu is None and self.raise_on_detach:
            raise RuntimeError("detach failed")
        self.context_menu = menu

    def setToolTip(self, tooltip: str) -> None:  # noqa: N802
        self.tooltip = tooltip

    def show(self) -> None:
        self.show_calls += 1
        self.visible = True

    def hide(self) -> None:
        self.hide_calls += 1
        self.visible = False
        if self.raise_on_hide:
            raise RuntimeError("hide failed")


@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    """Provide a Qt application for QMenu and QAction tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_no_tray_available_is_a_safe_noop(qt_app: QApplication) -> None:
    window = QWidget()
    factory_calls = 0

    def factory(_icon, _parent):  # type: ignore[no-untyped-def]
        nonlocal factory_calls
        factory_calls += 1
        return FakeTray()

    try:
        controller = TrayController(
            window,
            on_open=lambda: None,
            on_refresh=lambda: None,
            on_diagnostic=lambda: None,
            on_quit=lambda: None,
            availability_checker=lambda: False,
            tray_factory=factory,
        )

        assert controller.available is False
        assert controller.created is False
        assert factory_calls == 0
        controller.close()
        controller.close()
    finally:
        window.close()
        window.deleteLater()
        qt_app.processEvents()


def test_menu_actions_and_activation_are_deterministic(qt_app: QApplication) -> None:
    events: list[str] = []
    tray = FakeTray()
    received_icons: list[QIcon] = []
    window = QWidget()

    def factory(icon: QIcon, _parent: QWidget) -> FakeTray:
        received_icons.append(icon)
        return tray

    try:
        controller = TrayController(
            window,
            on_open=lambda: events.append("open"),
            on_refresh=lambda: events.append("refresh"),
            on_diagnostic=lambda: events.append("diagnostic"),
            on_quit=lambda: events.append("quit"),
            availability_checker=lambda: True,
            tray_factory=factory,
        )

        assert controller.available is True
        assert controller.created is True
        assert tray.visible is True
        assert tray.tooltip == "OpenBuds Manager"
        assert len(received_icons) == 1
        assert not received_icons[0].isNull()
        assert [action.text() for action in controller.menu.actions()] == [
            "Abrir ventana",
            "Actualizar",
            "Diagnóstico",
            "Salir",
        ]

        for action in controller.menu.actions():
            action.trigger()
        assert events == ["open", "refresh", "diagnostic", "quit"]

        tray.activated.emit(controller.trigger_reason)
        assert events[-1] == "open"

        controller.close()
        controller.close()
        assert tray.hide_calls == 1
        assert tray.visible is False
    finally:
        window.close()
        window.deleteLater()
        qt_app.processEvents()


def test_close_attempts_detach_and_hide_after_cleanup_errors(qt_app: QApplication) -> None:
    tray = FakeTray()
    window = QWidget()
    try:
        controller = TrayController(
            window,
            on_open=lambda: None,
            on_refresh=lambda: None,
            on_diagnostic=lambda: None,
            on_quit=lambda: None,
            availability_checker=lambda: True,
            tray_factory=lambda _icon, _parent: tray,
        )
        tray.raise_on_detach = True
        tray.raise_on_hide = True

        controller.close()
        controller.close()

        assert tray.hide_calls == 1
    finally:
        window.close()
        window.deleteLater()
        qt_app.processEvents()
