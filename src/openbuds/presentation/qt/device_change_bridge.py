"""Marshal read-only Bluetooth device changes into Qt notifications."""

from __future__ import annotations

import logging
import threading
from typing import Protocol

from PySide6.QtCore import QObject, Qt, Signal, Slot

from openbuds.domain.enums import DeviceChangeKind
from openbuds.domain.interfaces.observer import DeviceChangeCallback, Unsubscribe
from openbuds.domain.models import DeviceChangeEvent, DeviceInfo
from openbuds.presentation.formatting import connection_label, device_display_name

_LOGGER = logging.getLogger(__name__)
_SUBSCRIPTION_WARNING = "Las notificaciones automáticas de cambios no están disponibles."
_UNSUBSCRIPTION_WARNING = "No se pudo cerrar la suscripción de cambios de dispositivos."
_NOTIFICATION_WARNING = "No se pudo mostrar la notificación de cambio de dispositivo."


class DeviceChangeSource(Protocol):
    """Application boundary that provides read-only device change events."""

    def subscribe(self, callback: DeviceChangeCallback) -> Unsubscribe:
        """Subscribe to device changes and return an idempotent cleanup."""
        ...


class DesktopNotifierLike(Protocol):
    """Small notification boundary used by the bridge and its tests."""

    def notify(self, summary: str, body: str = "") -> None:
        """Show one best-effort desktop notification."""
        ...


class DeviceChangeBridge(QObject):
    """Deliver device changes on the Qt thread and notify meaningful events."""

    device_change_received = Signal(object)

    def __init__(
        self,
        source: DeviceChangeSource,
        notifier: DesktopNotifierLike,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._source = source
        self._notifier = notifier
        self._lock = threading.Lock()
        self._unsubscribe: Unsubscribe | None = None
        self._started = False
        self._closed = False
        self._subscribing = False
        self._bootstrap_thread: threading.Thread | None = None
        self.device_change_received.connect(
            self._on_device_change,
            Qt.ConnectionType.QueuedConnection,
        )

    def start(self) -> None:
        """Start the subscription once without blocking the Qt thread."""
        with self._lock:
            if self._closed or self._started:
                return
            self._started = True
            self._subscribing = True
            bootstrap_thread = threading.Thread(
                target=self._bootstrap_subscription,
                name="openbuds-device-change-bootstrap",
                daemon=True,
            )
            self._bootstrap_thread = bootstrap_thread

        try:
            bootstrap_thread.start()
        except Exception:
            with self._lock:
                self._started = False
                self._subscribing = False
            _LOGGER.warning(_SUBSCRIPTION_WARNING)

    def _bootstrap_subscription(self) -> None:
        """Perform the potentially blocking source subscription off the Qt thread."""
        try:
            unsubscribe = self._source.subscribe(self._on_repository_event)
        except Exception:
            with self._lock:
                self._started = False
                self._subscribing = False
            _LOGGER.warning(_SUBSCRIPTION_WARNING)
            return

        close_raced = False
        with self._lock:
            self._unsubscribe = unsubscribe
            self._subscribing = False
            if self._closed:
                self._unsubscribe = None
                close_raced = True

        if not close_raced:
            return
        self._unsubscribe_safely(unsubscribe)

    def close(self) -> None:
        """Close the bridge idempotently without touching Qt from the source callback."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            unsubscribe = self._unsubscribe
            self._unsubscribe = None

        if unsubscribe is None:
            return
        self._unsubscribe_safely(unsubscribe)

    @staticmethod
    def _unsubscribe_safely(unsubscribe: Unsubscribe) -> None:
        """Invoke an owned cleanup callback without holding the bridge lock."""
        try:
            unsubscribe()
        except Exception:
            _LOGGER.warning(_UNSUBSCRIPTION_WARNING)

    def _on_repository_event(self, event: DeviceChangeEvent) -> None:
        """Enqueue an event; all filtering and notification stays in the Qt slot."""
        with self._lock:
            if self._closed:
                return
            is_initial = self._subscribing
        self.device_change_received.emit((event, is_initial))

    @Slot(object)
    def _on_device_change(self, envelope: object) -> None:
        """Filter and notify a queued event on the bridge's Qt thread."""
        if not isinstance(envelope, tuple) or len(envelope) != 2:
            return
        event, is_initial = envelope
        with self._lock:
            closed = self._closed
        if closed or not isinstance(is_initial, bool) or is_initial:
            return
        if not isinstance(event, DeviceChangeEvent):
            return

        notification = self._notification_for(event)
        if notification is None:
            return
        summary, body = notification
        try:
            self._notifier.notify(summary, body)
        except Exception:
            _LOGGER.warning(_NOTIFICATION_WARNING)

    @staticmethod
    def _notification_for(event: DeviceChangeEvent) -> tuple[str, str] | None:
        """Build a privacy-safe notification matching the CLI watch wording.

        REMOVED uses ``Dispositivo desaparecido`` to match the CLI's
        ``[desapareció]`` event wording.
        """
        if event.kind is DeviceChangeKind.ADDED:
            assert event.current is not None
            return "Dispositivo detectado", _display_message(event.current)

        if event.kind is DeviceChangeKind.REMOVED:
            assert event.previous is not None
            return "Dispositivo desaparecido", device_display_name(event.previous)

        assert event.current is not None and event.previous is not None
        if event.current.connected == event.previous.connected:
            return None
        summary = "Dispositivo conectado" if event.current.connected else "Dispositivo desconectado"
        return summary, _display_message(event.current)


def _display_message(device: DeviceInfo) -> str:
    """Match the CLI watch format without exposing identifiers."""
    return f"{device_display_name(device)}: {connection_label(device)}"


__all__ = ["DeviceChangeBridge", "DeviceChangeSource", "DesktopNotifierLike"]
