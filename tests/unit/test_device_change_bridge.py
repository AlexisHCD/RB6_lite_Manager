"""Tests for the Qt bridge that presents Bluetooth device changes."""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable, Generator, Iterable

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, Qt
from PySide6.QtWidgets import QApplication

from openbuds.domain.enums import AddressType, ConnectionState, DeviceChangeKind, DeviceIcon
from openbuds.domain.models import DeviceChangeEvent, DeviceInfo
from openbuds.presentation.qt.device_change_bridge import DeviceChangeBridge


@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    """Provide one offscreen application for bridge tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def register_bridge(
    qt_app: QApplication,
) -> Generator[Callable[[DeviceChangeBridge], DeviceChangeBridge], None, None]:
    """Own bridge lifetime and drain Qt objects before the next test starts."""
    bridges: list[DeviceChangeBridge] = []

    def register(bridge: DeviceChangeBridge) -> DeviceChangeBridge:
        bridges.append(bridge)
        return bridge

    yield register

    for bridge in bridges:
        bridge.close()

    alive_threads: list[threading.Thread] = []
    for bridge in bridges:
        bootstrap_thread = bridge._bootstrap_thread
        if bootstrap_thread is None:
            continue
        bootstrap_thread.join(timeout=1.0)
        if bootstrap_thread.is_alive():
            alive_threads.append(bootstrap_thread)

    for bridge in bridges:
        bridge.device_change_received.disconnect()
        bridge.deleteLater()

    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qt_app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    assert not alive_threads, "DeviceChangeBridge bootstrap thread remained alive after cleanup"


class FakeWatch:
    """Capture the callback without touching a real Bluetooth repository."""

    def __init__(
        self,
        initial_events: Iterable[DeviceChangeEvent] = (),
        late_event: DeviceChangeEvent | None = None,
    ) -> None:
        self.callback = None
        self.initial_events = tuple(initial_events)
        self.late_event = late_event
        self.subscribe_calls = 0
        self.unsubscribe_calls = 0

    def subscribe(self, callback):
        self.subscribe_calls += 1
        self.callback = callback
        for event in self.initial_events:
            callback(event)

        active = True

        def unsubscribe() -> None:
            nonlocal active
            if active:
                active = False
                self.unsubscribe_calls += 1
                if self.late_event is not None:
                    callback(self.late_event)

        return unsubscribe

    def emit(self, event: DeviceChangeEvent) -> None:
        assert self.callback is not None
        self.callback(event)


class BlockingSubscribeWatch:
    """Hold subscription setup at a deterministic synchronization point."""

    def __init__(self) -> None:
        self.callback = None
        self.subscribe_entered = threading.Event()
        self.release_subscribe = threading.Event()
        self.subscribe_returned = threading.Event()
        self.unsubscribe_called = threading.Event()
        self.unsubscribe_calls = 0
        self.unsubscribe_lock_states: list[bool] = []
        self.lock_probe: threading.Lock | None = None

    def subscribe(self, callback):
        self.callback = callback
        self.subscribe_entered.set()
        self.release_subscribe.wait()
        self.subscribe_returned.set()

        def unsubscribe() -> None:
            self.unsubscribe_calls += 1
            if self.lock_probe is not None:
                self.unsubscribe_lock_states.append(self.lock_probe.locked())
            self.unsubscribe_called.set()

        return unsubscribe


class RecordingNotifier:
    """Record notifications and the thread that handled them."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []

    def notify(self, summary: str, body: str = "") -> None:
        self.calls.append((summary, body, threading.get_ident()))


class WarningEventHandler(logging.Handler):
    """Capture a warning without racing the bootstrap thread in a test."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []
        self.warning_seen = threading.Event()

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())
        self.warning_seen.set()


def _process_events_until(
    predicate: Callable[[], bool],
    *,
    description: str,
    timeout_seconds: float = 0.5,
) -> None:
    """Process bounded Qt event-loop slices until a condition becomes true."""
    deadline = time.monotonic() + timeout_seconds
    while not predicate():
        remaining_seconds = deadline - time.monotonic()
        if remaining_seconds <= 0:
            break
        small_timeout_ms = min(10, max(1, int(remaining_seconds * 1000)))
        QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, small_timeout_ms)

    assert predicate(), f"Timed out after {timeout_seconds:.3f}s waiting for {description}"


def _wait_for_bootstrap(bridge: DeviceChangeBridge) -> None:
    """Wait for a fast fake source without introducing timing sleeps."""
    bootstrap_thread = bridge._bootstrap_thread
    assert bootstrap_thread is not None
    bootstrap_thread.join(timeout=1.0)
    assert bootstrap_thread.is_alive() is False


def _device(*, connected: bool = False, alias: str = "Buds") -> DeviceInfo:
    return DeviceInfo(
        object_path="/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF",
        address="AA:BB:CC:DD:EE:FF",
        name="Redmi Buds",
        alias=alias,
        icon=DeviceIcon.AUDIO_HEADSET,
        address_type=AddressType.PUBLIC,
        paired=True,
        connected=connected,
        trusted=False,
        blocked=False,
        services_resolved=True,
        connection_state=(ConnectionState.CONNECTED if connected else ConnectionState.DISCONNECTED),
    )


def test_worker_callback_is_marshaled_to_qt_before_notifying(
    qt_app: QCoreApplication,
    register_bridge: Callable[[DeviceChangeBridge], DeviceChangeBridge],
) -> None:
    watch = FakeWatch()
    notifier = RecordingNotifier()
    bridge = register_bridge(DeviceChangeBridge(watch, notifier))
    bridge.start()
    _wait_for_bootstrap(bridge)

    callback_thread_id: int | None = None

    def emit_from_worker() -> None:
        nonlocal callback_thread_id
        callback_thread_id = threading.get_ident()
        assert watch.callback is not None
        watch.callback(DeviceChangeEvent(DeviceChangeKind.ADDED, _device(), None))

    worker = threading.Thread(target=emit_from_worker)
    worker.start()
    worker.join()
    _process_events_until(
        lambda: len(notifier.calls) == 1,
        description="the worker-marshalled notification",
    )

    try:
        assert callback_thread_id is not None
        assert len(notifier.calls) == 1
        assert notifier.calls[0][0] == "Dispositivo detectado"
        assert notifier.calls[0][1] == "Buds: emparejado"
        notification_thread_id = notifier.calls[0][2]
        assert notification_thread_id == threading.get_ident()
        assert notification_thread_id != callback_thread_id
    finally:
        bridge.close()


def test_initialization_batch_is_suppressed_but_later_event_is_notified(
    qt_app: QCoreApplication,
    register_bridge: Callable[[DeviceChangeBridge], DeviceChangeBridge],
) -> None:
    initial_previous = _device(alias="Inicial")
    initial_current = _device(connected=True, alias="Inicial")
    initial_events = (
        DeviceChangeEvent(DeviceChangeKind.ADDED, _device(alias="Aparece"), None),
        DeviceChangeEvent(DeviceChangeKind.UPDATED, initial_current, initial_previous),
        DeviceChangeEvent(DeviceChangeKind.REMOVED, None, _device(alias="Desaparece")),
    )
    watch = FakeWatch(initial_events)
    notifier = RecordingNotifier()
    bridge = register_bridge(DeviceChangeBridge(watch, notifier))
    bridge.start()
    _wait_for_bootstrap(bridge)

    qt_app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents)
    assert notifier.calls == []

    watch.emit(DeviceChangeEvent(DeviceChangeKind.ADDED, _device(alias="Posterior"), None))
    _process_events_until(
        lambda: len(notifier.calls) == 1,
        description="the post-initialization notification",
    )

    try:
        assert len(notifier.calls) == 1
        assert notifier.calls[0][0] == "Dispositivo detectado"
        assert notifier.calls[0][1] == "Posterior: emparejado"
    finally:
        bridge.close()


def test_event_after_subscription_boundary_is_not_suppressed_before_qt_processing(
    qt_app: QCoreApplication,
    register_bridge: Callable[[DeviceChangeBridge], DeviceChangeBridge],
) -> None:
    watch = FakeWatch()
    notifier = RecordingNotifier()
    bridge = register_bridge(DeviceChangeBridge(watch, notifier))
    bridge.start()
    _wait_for_bootstrap(bridge)

    # start() returned, so the subscription boundary has passed; Qt is still idle.
    worker_ready = threading.Barrier(2)

    def emit_from_worker() -> None:
        worker_ready.wait()
        watch.emit(DeviceChangeEvent(DeviceChangeKind.ADDED, _device(alias="Después"), None))

    worker = threading.Thread(target=emit_from_worker)
    worker.start()
    worker_ready.wait()
    worker.join()

    try:
        _process_events_until(
            lambda: len(notifier.calls) == 1,
            description="the post-subscription notification",
        )
        assert len(notifier.calls) == 1
        assert notifier.calls[0][0] == "Dispositivo detectado"
        assert notifier.calls[0][1] == "Después: emparejado"
    finally:
        bridge.close()


def test_only_connection_transitions_and_add_remove_are_notified(
    qt_app: QCoreApplication,
    register_bridge: Callable[[DeviceChangeBridge], DeviceChangeBridge],
) -> None:
    watch = FakeWatch()
    notifier = RecordingNotifier()
    bridge = register_bridge(DeviceChangeBridge(watch, notifier))
    bridge.start()
    _wait_for_bootstrap(bridge)
    qt_app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents)

    same_previous = _device(alias="Antes")
    same_current = _device(alias="Después")
    disconnected = _device(connected=False)
    connected = _device(connected=True)
    watch.emit(DeviceChangeEvent(DeviceChangeKind.UPDATED, same_current, same_previous))
    watch.emit(DeviceChangeEvent(DeviceChangeKind.UPDATED, connected, disconnected))
    watch.emit(DeviceChangeEvent(DeviceChangeKind.UPDATED, disconnected, connected))
    watch.emit(
        DeviceChangeEvent(
            DeviceChangeKind.ADDED,
            _device(alias="Nuevo 00:11:22:33:44:55\n/org/bluez/hci0/dev_secret"),
            None,
        )
    )
    watch.emit(DeviceChangeEvent(DeviceChangeKind.REMOVED, None, _device(alias="Quitado")))
    _process_events_until(
        lambda: len(notifier.calls) == 4,
        description="all device-change notifications",
    )

    try:
        assert [summary for summary, _body, _thread_id in notifier.calls] == [
            "Dispositivo conectado",
            "Dispositivo desconectado",
            "Dispositivo detectado",
            "Dispositivo desaparecido",
        ]
        assert "00:11:22:33:44:55" not in notifier.calls[2][1]
        assert "/org/bluez/hci0/dev_secret" not in notifier.calls[2][1]
    finally:
        bridge.close()


def test_close_is_idempotent_and_late_queued_events_are_ignored(
    qt_app: QCoreApplication,
    register_bridge: Callable[[DeviceChangeBridge], DeviceChangeBridge],
) -> None:
    watch = FakeWatch(
        late_event=DeviceChangeEvent(DeviceChangeKind.ADDED, _device(alias="Tarde"), None)
    )
    notifier = RecordingNotifier()
    bridge = register_bridge(DeviceChangeBridge(watch, notifier))
    bridge.start()
    bridge.start()
    _wait_for_bootstrap(bridge)
    qt_app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents)

    watch.emit(DeviceChangeEvent(DeviceChangeKind.ADDED, _device(), None))
    bridge.close()
    bridge.close()
    qt_app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents)
    qt_app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents)

    assert notifier.calls == []
    assert watch.subscribe_calls == 1
    assert watch.unsubscribe_calls == 1


class FailingNotifier:
    """Notifier fake whose failure must remain local to the bridge."""

    def notify(self, _summary: str, _body: str = "") -> None:
        raise RuntimeError("notification service unavailable")


def test_notifier_failure_does_not_escape_qt_dispatch(
    qt_app: QCoreApplication,
    register_bridge: Callable[[DeviceChangeBridge], DeviceChangeBridge],
) -> None:
    watch = FakeWatch()
    bridge = register_bridge(DeviceChangeBridge(watch, FailingNotifier()))
    bridge.start()
    _wait_for_bootstrap(bridge)
    qt_app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents)

    watch.emit(DeviceChangeEvent(DeviceChangeKind.ADDED, _device(), None))
    qt_app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents)

    bridge.close()


def test_start_returns_while_source_subscription_is_blocked(
    register_bridge: Callable[[DeviceChangeBridge], DeviceChangeBridge],
) -> None:
    watch = BlockingSubscribeWatch()
    bridge = register_bridge(DeviceChangeBridge(watch, RecordingNotifier()))
    start_returned = threading.Event()
    starter = threading.Thread(
        target=lambda: (bridge.start(), start_returned.set()),
        daemon=True,
    )
    starter.start()

    try:
        assert watch.subscribe_entered.wait(timeout=1.0)
        assert start_returned.wait(timeout=1.0)
        assert watch.unsubscribe_called.is_set() is False
    finally:
        watch.release_subscribe.set()
        bridge.close()

    assert watch.unsubscribe_called.wait(timeout=1.0)
    assert watch.unsubscribe_calls == 1


def test_source_failure_logs_only_generic_warning_and_keeps_bridge_usable(
    register_bridge: Callable[[DeviceChangeBridge], DeviceChangeBridge],
) -> None:
    class FailingWatch:
        def subscribe(self, _callback):
            raise RuntimeError("private source detail")

    logger = logging.getLogger("openbuds.presentation.qt.device_change_bridge")
    handler = WarningEventHandler()
    logger.addHandler(handler)
    bridge = register_bridge(
        DeviceChangeBridge(FailingWatch(), RecordingNotifier())  # type: ignore[arg-type]
    )
    try:
        bridge.start()
        assert handler.warning_seen.wait(timeout=1.0)
        assert handler.messages == [
            "Las notificaciones automáticas de cambios no están disponibles."
        ]
        bridge.close()
    finally:
        logger.removeHandler(handler)


def test_close_during_blocked_subscribe_releases_unsubscribe_once_and_drops_callbacks(
    register_bridge: Callable[[DeviceChangeBridge], DeviceChangeBridge],
) -> None:
    watch = BlockingSubscribeWatch()
    bridge = register_bridge(DeviceChangeBridge(watch, RecordingNotifier()))
    watch.lock_probe = bridge._lock
    start_returned = threading.Event()
    starter = threading.Thread(
        target=lambda: (bridge.start(), start_returned.set()),
        daemon=True,
    )
    starter.start()

    emitted_signal = threading.Event()
    bridge.device_change_received.connect(
        lambda _envelope: emitted_signal.set(),
        Qt.ConnectionType.DirectConnection,
    )

    try:
        assert watch.subscribe_entered.wait(timeout=1.0)
        bridge.close()
        assert watch.callback is not None
        watch.callback(DeviceChangeEvent(DeviceChangeKind.ADDED, _device(), None))
        assert emitted_signal.is_set() is False
        assert start_returned.wait(timeout=1.0)
    finally:
        watch.release_subscribe.set()

    assert watch.unsubscribe_called.wait(timeout=1.0)
    assert watch.unsubscribe_calls == 1
    assert watch.unsubscribe_lock_states == [False]


def test_direct_signal_observer_can_reenter_close_without_lock_deadlock(
    qt_app: QCoreApplication,
    register_bridge: Callable[[DeviceChangeBridge], DeviceChangeBridge],
) -> None:
    watch = FakeWatch()
    bridge = register_bridge(DeviceChangeBridge(watch, RecordingNotifier()))
    bridge.start()
    _wait_for_bootstrap(bridge)

    close_returned = threading.Event()

    def close_from_signal(_envelope: object) -> None:
        bridge.close()
        close_returned.set()

    bridge.device_change_received.connect(
        close_from_signal,
        Qt.ConnectionType.DirectConnection,
    )
    worker = threading.Thread(
        target=lambda: watch.emit(DeviceChangeEvent(DeviceChangeKind.ADDED, _device(), None)),
        daemon=True,
    )
    worker.start()
    worker.join(timeout=1.0)

    if worker.is_alive():
        pytest.fail("direct signal observer could not re-enter close()")

    try:
        assert close_returned.is_set()
        assert watch.unsubscribe_calls == 1
    finally:
        bridge.close()
