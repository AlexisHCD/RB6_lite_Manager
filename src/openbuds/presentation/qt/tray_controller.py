"""Optional Qt system-tray controller for the desktop presentation layer."""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import suppress
from typing import Protocol, cast

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QStyle, QSystemTrayIcon, QWidget

_LOGGER = logging.getLogger(__name__)
_TRAY_WARNING = "La bandeja del sistema no está disponible."


class _ActivationSignal(Protocol):
    """Minimal Qt signal surface used by a tray icon."""

    def connect(self, slot: Callable[[object], None]) -> object:
        """Connect a tray activation handler."""


class _TrayIcon(Protocol):
    """Minimal tray icon surface, also convenient for unit-test fakes."""

    activated: _ActivationSignal

    def setContextMenu(self, menu: QMenu | None) -> None:  # noqa: N802
        """Assign the context menu."""

    def setToolTip(self, tooltip: str) -> None:  # noqa: N802
        """Set the desktop tooltip."""

    def show(self) -> None:
        """Show the tray icon."""

    def hide(self) -> None:
        """Hide the tray icon."""


TrayFactory = Callable[[QIcon, QWidget], _TrayIcon]


def _create_tray(icon: QIcon, parent: QWidget) -> _TrayIcon:
    """Create the concrete Qt tray icon."""
    return cast(_TrayIcon, QSystemTrayIcon(icon, parent))


class TrayController:
    """Own an optional tray icon and delegate all actions to window callbacks."""

    def __init__(
        self,
        window: QWidget,
        *,
        on_open: Callable[[], None],
        on_refresh: Callable[[], None],
        on_diagnostic: Callable[[], None],
        on_quit: Callable[[], None],
        availability_checker: Callable[[], bool] | None = None,
        tray_factory: TrayFactory | None = None,
    ) -> None:
        """Create and show the tray only when the desktop environment supports it."""
        self._window = window
        self._on_open = on_open
        self._on_refresh = on_refresh
        self._on_diagnostic = on_diagnostic
        self._on_quit = on_quit
        self._availability_checker = availability_checker or QSystemTrayIcon.isSystemTrayAvailable
        self._tray_factory = tray_factory or _create_tray
        self._tray: _TrayIcon | None = None
        self._menu: QMenu | None = None
        self._available = False
        self._created = False
        self._closed = False
        self._initialize()

    @property
    def available(self) -> bool:
        """Return whether the desktop reports a usable system tray."""
        return self._available

    @property
    def created(self) -> bool:
        """Return whether this controller created a tray icon."""
        return self._created

    @property
    def menu(self) -> QMenu | None:
        """Return the menu for inspection or UI tests."""
        return self._menu

    @property
    def trigger_reason(self) -> QSystemTrayIcon.ActivationReason:
        """Return the activation reason that opens the main window."""
        return QSystemTrayIcon.ActivationReason.Trigger

    def _initialize(self) -> None:
        try:
            self._available = bool(self._availability_checker())
        except Exception:
            self._available = False
        if not self._available:
            return

        tray: _TrayIcon | None = None
        try:
            tray = self._tray_factory(
                self._window.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume),
                self._window,
            )
            menu = QMenu(self._window)
            self._add_action(menu, "Abrir ventana", self._on_open)
            self._add_action(menu, "Actualizar", self._on_refresh)
            self._add_action(menu, "Diagnóstico", self._on_diagnostic)
            self._add_action(menu, "Salir", self._on_quit)
            tray.setContextMenu(menu)
            tray.setToolTip("OpenBuds Manager")
            tray.activated.connect(self._on_activated)
            tray.show()
        except Exception:
            if tray is not None:
                with suppress(Exception):
                    tray.hide()
            _LOGGER.warning(_TRAY_WARNING)
            return

        self._tray = tray
        self._menu = menu
        self._created = True

    @staticmethod
    def _add_action(menu: QMenu, label: str, callback: Callable[[], None]) -> QAction:
        action = QAction(label, menu)
        action.triggered.connect(lambda _checked=False: callback())
        menu.addAction(action)
        return action

    def _on_activated(self, reason: object) -> None:
        if self._closed:
            return
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._on_open()

    def close(self) -> None:
        """Hide and detach the tray icon; safe to call repeatedly."""
        if self._closed:
            return
        self._closed = True
        tray = self._tray
        self._tray = None
        self._menu = None
        if tray is not None:
            with suppress(Exception):
                tray.setContextMenu(None)
            with suppress(Exception):
                tray.hide()


__all__ = ["TrayController"]
