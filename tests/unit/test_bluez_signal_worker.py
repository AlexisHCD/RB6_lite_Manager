"""TDD RED contract for the threaded BlueZ signal worker."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import pytest

from openbuds.core.errors import BluetoothError
from openbuds.infrastructure.bluez.dbus_protocol import SignalEvent, _SignalWorker


class FakeMainContext:
    """Small GLib context backed by a condition and a real worker thread."""

    latest: FakeMainContext | None = None

    def __init__(self) -> None:
        self._commands: deque[tuple[Callable[..., Any], tuple[Any, ...]]] = deque()
        self._condition = threading.Condition()
        self._stopped = False
        FakeMainContext.latest = self

    @classmethod
    def new(cls) -> FakeMainContext:
        return cls()

    def invoke_full(self, _priority: int, callback: Callable[..., Any], *args: Any) -> None:
        with self._condition:
            self._commands.append((callback, args))
            self._condition.notify()

    def push_thread_default(self) -> None:
        pass

    def pop_thread_default(self) -> None:
        pass

    def dispatch(self, timeout: float) -> bool:
        with self._condition:
            if not self._commands and not self._stopped:
                self._condition.wait(timeout)
            if not self._commands:
                return not self._stopped
            callback, args = self._commands.popleft()
        callback(*args)
        return True

    def stop(self) -> None:
        with self._condition:
            self._stopped = True
            self._condition.notify_all()


class FakeMainLoop:
    def __init__(self, context: FakeMainContext) -> None:
        self.context = context
        self.started = threading.Event()
        self._quit = threading.Event()

    @classmethod
    def new(cls, context: FakeMainContext, _running: bool) -> FakeMainLoop:
        return cls(context)

    def run(self) -> None:
        self.started.set()
        while not self._quit.is_set():
            if not self.context.dispatch(0.05):
                break

    def quit(self) -> None:
        self._quit.set()
        self.context.stop()


class FakeGLib:
    class Error(Exception):
        pass

    PRIORITY_DEFAULT = 0
    MainContext = FakeMainContext
    MainLoop = FakeMainLoop


class RaisingMainContext(FakeMainContext):
    error = RuntimeError("context creation failed")

    @classmethod
    def new(cls) -> FakeMainContext:
        raise cls.error


class GateMainContext(FakeMainContext):
    gate = threading.Event()
    created = threading.Event()

    @classmethod
    def new(cls) -> FakeMainContext:
        cls.gate.wait()
        context = cls()
        cls.created.set()
        return context


class RaisingContextGLib(FakeGLib):
    MainContext = RaisingMainContext


class GatedContextGLib(FakeGLib):
    MainContext = GateMainContext


class FakeGio:
    class DBusSignalFlags:
        NONE = 0


@dataclass(frozen=True)
class SignalSubscription:
    callback: Callable[..., Any]
    args: tuple[Any, ...]
    thread_id: int


class FakeConnection:
    def __init__(self, fail_on_subscribe_call: int | None = None) -> None:
        self.subscriptions: list[SignalSubscription] = []
        self.active_subscriptions: dict[int, SignalSubscription] = {}
        self.unsubscribe_calls: list[tuple[int, int]] = []
        self.fail_on_subscribe_call = fail_on_subscribe_call
        self.subscribe_calls = 0
        self._lock = threading.Lock()
        self._next_id = 1

    def signal_subscribe(self, *args: Any) -> int:
        callback = args[6]
        with self._lock:
            self.subscribe_calls += 1
            if self.subscribe_calls == self.fail_on_subscribe_call:
                raise RuntimeError("second filter failed")
            subscription_id = self._next_id
            self._next_id += 1
            record = SignalSubscription(callback, args, threading.get_ident())
            self.subscriptions.append(record)
            self.active_subscriptions[subscription_id] = record
        return subscription_id

    def signal_unsubscribe(self, subscription_id: int) -> None:
        with self._lock:
            self.unsubscribe_calls.append((subscription_id, threading.get_ident()))
            self.active_subscriptions.pop(subscription_id, None)

    def emit(
        self,
        sender: object,
        object_path: object,
        interface_name: object,
        signal_name: object,
        parameters: object = None,
    ) -> None:
        context = FakeMainContext.latest
        assert context is not None
        with self._lock:
            callbacks = [
                subscription.callback
                for subscription in self.active_subscriptions.values()
                if subscription.args[1] == interface_name and subscription.args[2] == signal_name
            ]
        for callback in callbacks:
            context.invoke_full(
                0, callback, self, sender, object_path, interface_name, signal_name, parameters
            )


class FakeProxy:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def get_connection(self) -> FakeConnection:
        return self.connection


@pytest.fixture
def signal_setup() -> Iterator[tuple[_SignalWorker, FakeConnection]]:
    connection = FakeConnection()
    worker = _SignalWorker(
        FakeGio,
        FakeGLib,
        FakeProxy(connection),
        operation_timeout=0.5,
    )
    worker.start()
    try:
        yield worker, connection
    finally:
        worker.close()


@pytest.fixture(autouse=True)
def reset_fake_context_globals() -> Iterator[None]:
    FakeMainContext.latest = None
    GateMainContext.gate = threading.Event()
    GateMainContext.created = threading.Event()
    yield
    FakeMainContext.latest = None


def flush_worker_context() -> None:
    """Wait until all commands queued before this marker have run."""
    context = FakeMainContext.latest
    assert context is not None
    flushed = threading.Event()
    context.invoke_full(0, flushed.set)
    assert flushed.wait(0.5)


def subscribe_once(
    worker: _SignalWorker,
    callback: Callable[[SignalEvent], None] | None = None,
) -> int:
    return worker.subscribe(callback or (lambda _event: None))


def test_first_subscribe_registers_three_filters_on_worker_thread(
    signal_setup: tuple[_SignalWorker, FakeConnection],
) -> None:
    worker, connection = signal_setup
    test_thread = threading.get_ident()

    subscribe_once(worker)

    assert len(connection.subscriptions) == 3
    assert {record.thread_id for record in connection.subscriptions}.isdisjoint({test_thread})
    assert [record.args[:6] for record in connection.subscriptions] == [
        (
            "org.bluez",
            "org.freedesktop.DBus.ObjectManager",
            "InterfacesAdded",
            None,
            None,
            FakeGio.DBusSignalFlags.NONE,
        ),
        (
            "org.bluez",
            "org.freedesktop.DBus.ObjectManager",
            "InterfacesRemoved",
            None,
            None,
            FakeGio.DBusSignalFlags.NONE,
        ),
        (
            "org.bluez",
            "org.freedesktop.DBus.Properties",
            "PropertiesChanged",
            None,
            None,
            FakeGio.DBusSignalFlags.NONE,
        ),
    ]


def test_subscribe_on_ready_is_a_worker_thread_barrier_after_all_filters_are_active(
    signal_setup: tuple[_SignalWorker, FakeConnection],
) -> None:
    worker, connection = signal_setup
    caller_thread = threading.get_ident()
    hook_entered = threading.Event()
    release_hook = threading.Event()
    hook_calls: list[tuple[int, int]] = []
    subscribe_errors: list[BaseException] = []

    def on_ready() -> None:
        hook_calls.append((threading.get_ident(), len(connection.active_subscriptions)))
        hook_entered.set()
        assert release_hook.wait(0.5)

    result: list[int] = []

    def subscribe() -> None:
        try:
            result.append(worker.subscribe(lambda _event: None, on_ready=on_ready))
        except BaseException as exc:
            subscribe_errors.append(exc)

    subscribe_thread = threading.Thread(target=subscribe)
    subscribe_thread.start()
    assert hook_entered.wait(0.5)
    assert subscribe_thread.is_alive()
    release_hook.set()
    subscribe_thread.join(0.5)

    assert not subscribe_thread.is_alive()
    assert subscribe_errors == []
    assert result == [1]
    assert hook_calls == [(connection.subscriptions[0].thread_id, 3)]
    assert hook_calls[0][0] != caller_thread


def test_subscribe_on_ready_failure_rolls_back_filters_and_stops_worker(
    signal_setup: tuple[_SignalWorker, FakeConnection],
) -> None:
    worker, connection = signal_setup
    callback_calls: list[SignalEvent] = []

    def on_ready() -> None:
        raise RuntimeError("ready hook failed")

    with pytest.raises(RuntimeError, match="ready hook failed") as raised:
        worker.subscribe(callback_calls.append, on_ready=on_ready)

    assert raised.value.__cause__ is None
    assert worker.is_closed
    assert len(connection.unsubscribe_calls) == 3
    assert {thread_id for _subscription_id, thread_id in connection.unsubscribe_calls} == {
        connection.subscriptions[0].thread_id
    }
    assert len(connection.active_subscriptions) == 0

    connection.emit(
        "org.bluez", "/org/bluez/hci0", "org.freedesktop.DBus.ObjectManager", "InterfacesAdded"
    )
    assert callback_calls == []


def test_subscribe_without_on_ready_keeps_backward_path(
    signal_setup: tuple[_SignalWorker, FakeConnection],
) -> None:
    worker, _connection = signal_setup

    assert worker.subscribe(lambda _event: None) == 1


def test_two_callbacks_have_distinct_logical_ids_and_share_bus_subscriptions(
    signal_setup: tuple[_SignalWorker, FakeConnection],
) -> None:
    worker, connection = signal_setup

    first = subscribe_once(worker)
    second = subscribe_once(worker)

    assert first != second
    assert len(connection.subscriptions) == 3


def test_valid_signal_becomes_event_and_callbacks_run_in_registration_order(
    signal_setup: tuple[_SignalWorker, FakeConnection],
) -> None:
    worker, connection = signal_setup
    received: list[tuple[str, SignalEvent, int]] = []
    done = threading.Event()

    def first(event: SignalEvent) -> None:
        received.append(("first", event, threading.get_ident()))

    def second(event: SignalEvent) -> None:
        received.append(("second", event, threading.get_ident()))
        done.set()

    worker.subscribe(first)
    worker.subscribe(second)
    connection.emit(
        "org.bluez",
        "/org/bluez/hci0",
        "org.freedesktop.DBus.ObjectManager",
        "InterfacesAdded",
        ("/org/bluez/hci0", {}),
    )

    assert done.wait(0.5)
    assert [name for name, _event, _thread in received] == ["first", "second"]
    assert received[0][1] == SignalEvent(
        "org.freedesktop.DBus.ObjectManager", "InterfacesAdded", "/org/bluez/hci0"
    )
    assert len({thread_id for _name, _event, thread_id in received}) == 1
    assert received[0][2] != threading.get_ident()


def test_failing_callback_is_logged_and_does_not_block_next_callback(
    signal_setup: tuple[_SignalWorker, FakeConnection], caplog: pytest.LogCaptureFixture
) -> None:
    worker, connection = signal_setup
    called = threading.Event()

    def failing(_event: SignalEvent) -> None:
        raise RuntimeError("callback boom")

    def succeeding(_event: SignalEvent) -> None:
        called.set()

    worker.subscribe(failing)
    worker.subscribe(succeeding)
    with caplog.at_level(logging.ERROR):
        connection.emit(
            "org.bluez",
            "/org/bluez/hci0",
            "org.freedesktop.DBus.ObjectManager",
            "InterfacesAdded",
        )
        assert called.wait(0.5)

    assert "callback boom" in caplog.text


@pytest.mark.parametrize(
    ("sender", "object_path", "interface_name", "signal_name"),
    [
        ("org.bluez", 42, "org.freedesktop.DBus.ObjectManager", "InterfacesAdded"),
        ("org.bluez", "/org/bluez/hci0", "org.freedesktop.DBus.ObjectManager", "Unknown"),
    ],
)
def test_invalid_metadata_or_unsupported_pair_is_ignored(
    signal_setup: tuple[_SignalWorker, FakeConnection],
    sender: object,
    object_path: object,
    interface_name: object,
    signal_name: object,
) -> None:
    worker, connection = signal_setup
    received: list[SignalEvent] = []
    worker.subscribe(received.append)

    connection.emit(sender, object_path, interface_name, signal_name)
    flush_worker_context()

    assert received == []


def test_unsubscribe_keeps_other_callback_and_last_removes_three_bus_filters(
    signal_setup: tuple[_SignalWorker, FakeConnection],
) -> None:
    worker, connection = signal_setup
    first_received: list[SignalEvent] = []
    second_received: list[SignalEvent] = []
    second_done = threading.Event()
    first = worker.subscribe(first_received.append)

    def receive_second(event: SignalEvent) -> None:
        second_received.append(event)
        second_done.set()

    second = worker.subscribe(receive_second)

    worker.unsubscribe(first)
    connection.emit(
        "org.bluez", "/org/bluez/hci0", "org.freedesktop.DBus.ObjectManager", "InterfacesAdded"
    )
    assert second_done.wait(0.5)
    assert first_received == []

    worker.unsubscribe(second)
    assert len(connection.unsubscribe_calls) == 3
    assert len({thread_id for _subscription_id, thread_id in connection.unsubscribe_calls}) == 1
    assert all(
        thread_id != threading.get_ident()
        for _subscription_id, thread_id in connection.unsubscribe_calls
    )

    connection.emit(
        "org.bluez", "/org/bluez/hci0", "org.freedesktop.DBus.ObjectManager", "InterfacesAdded"
    )
    assert len(second_received) == 1


def test_close_is_idempotent_stops_worker_once_and_never_closes_proxy_or_connection(
    signal_setup: tuple[_SignalWorker, FakeConnection],
) -> None:
    worker, connection = signal_setup
    received: list[SignalEvent] = []
    worker.subscribe(received.append)

    worker.close()
    worker.close()

    assert len(connection.unsubscribe_calls) == 3
    assert len({thread_id for _subscription_id, thread_id in connection.unsubscribe_calls}) == 1
    assert all(
        thread_id != threading.get_ident()
        for _subscription_id, thread_id in connection.unsubscribe_calls
    )

    connection.emit(
        "org.bluez", "/org/bluez/hci0", "org.freedesktop.DBus.ObjectManager", "InterfacesAdded"
    )
    assert received == []


def test_unknown_unsubscribe_while_active_does_not_stop_worker_and_double_last_is_noop(
    signal_setup: tuple[_SignalWorker, FakeConnection],
) -> None:
    worker, connection = signal_setup
    received: list[SignalEvent] = []
    delivered = threading.Event()

    def callback(event: SignalEvent) -> None:
        received.append(event)
        delivered.set()

    subscription_id = worker.subscribe(callback)
    worker.unsubscribe(999_999)
    connection.emit(
        "org.bluez", "/org/bluez/hci0", "org.freedesktop.DBus.ObjectManager", "InterfacesAdded"
    )
    assert delivered.wait(0.5)

    worker.unsubscribe(subscription_id)
    unsubscribe_count = len(connection.unsubscribe_calls)
    started = time.monotonic()
    worker.unsubscribe(subscription_id)
    elapsed = time.monotonic() - started

    assert elapsed < 0.25
    assert len(connection.unsubscribe_calls) == unsubscribe_count
    assert len(received) == 1


def test_callback_can_unsubscribe_itself_from_worker_without_deadlock(
    signal_setup: tuple[_SignalWorker, FakeConnection],
) -> None:
    worker, connection = signal_setup
    received: list[SignalEvent] = []
    done = threading.Event()
    subscription_id = 0

    def callback(event: SignalEvent) -> None:
        received.append(event)
        worker.unsubscribe(subscription_id)
        done.set()

    subscription_id = worker.subscribe(callback)
    connection.emit(
        "org.bluez", "/org/bluez/hci0", "org.freedesktop.DBus.ObjectManager", "InterfacesAdded"
    )
    assert done.wait(0.5)
    connection.emit(
        "org.bluez", "/org/bluez/hci0", "org.freedesktop.DBus.ObjectManager", "InterfacesAdded"
    )

    assert len(received) == 1


def test_reentrant_subscribe_is_deferred_until_next_signal(
    signal_setup: tuple[_SignalWorker, FakeConnection],
) -> None:
    worker, connection = signal_setup
    received: list[str] = []
    second_done = threading.Event()

    def second(_event: SignalEvent) -> None:
        received.append("second")
        second_done.set()

    def first(_event: SignalEvent) -> None:
        received.append("first")
        worker.subscribe(second)

    worker.subscribe(first)
    connection.emit(
        "org.bluez", "/org/bluez/hci0", "org.freedesktop.DBus.ObjectManager", "InterfacesAdded"
    )
    flush_worker_context()
    assert received == ["first"]

    connection.emit(
        "org.bluez", "/org/bluez/hci0", "org.freedesktop.DBus.ObjectManager", "InterfacesAdded"
    )
    assert second_done.wait(0.5)
    assert received == ["first", "first", "second"]


def test_partial_bus_registration_rolls_back_and_stops_worker() -> None:
    connection = FakeConnection(fail_on_subscribe_call=2)
    worker = _SignalWorker(FakeGio, FakeGLib, FakeProxy(connection), operation_timeout=0.2)
    worker.start()

    try:
        with pytest.raises(BluetoothError, match="registrar") as raised:
            worker.subscribe(lambda _event: None)

        assert isinstance(raised.value.__cause__, RuntimeError)
        assert [
            subscription_id for subscription_id, _thread_id in connection.unsubscribe_calls
        ] == [1]
        assert len(connection.active_subscriptions) == 0
        worker.close()
        assert [
            subscription_id for subscription_id, _thread_id in connection.unsubscribe_calls
        ] == [1]
    finally:
        worker.close()


def test_main_context_failure_is_wrapped_without_deadlock() -> None:
    worker = _SignalWorker(
        FakeGio, RaisingContextGLib, FakeProxy(FakeConnection()), operation_timeout=0.2
    )

    with pytest.raises(BluetoothError, match="iniciar") as raised:
        worker.start()

    assert raised.value.__cause__ is RaisingMainContext.error
    worker.close()


def test_startup_timeout_can_be_released_and_worker_finishes() -> None:
    connection = FakeConnection()
    worker = _SignalWorker(FakeGio, GatedContextGLib, FakeProxy(connection), operation_timeout=0.05)

    started = time.monotonic()
    with pytest.raises(BluetoothError, match="agotado"):
        worker.start()
    assert time.monotonic() - started < 0.5

    GateMainContext.gate.set()
    assert GateMainContext.created.wait(0.5)
    worker.close()


def test_subscribe_after_close_fails_immediately_as_closed() -> None:
    worker = _SignalWorker(FakeGio, FakeGLib, FakeProxy(FakeConnection()), operation_timeout=0.2)
    worker.start()
    worker.close()

    started = time.monotonic()
    with pytest.raises(BluetoothError, match="cerrado"):
        worker.subscribe(lambda _event: None)
    assert time.monotonic() - started < 0.1


def test_close_is_idempotent_before_and_after_worker_has_stopped(
    signal_setup: tuple[_SignalWorker, FakeConnection],
) -> None:
    worker, connection = signal_setup
    worker.close()
    worker.close()
    assert connection.unsubscribe_calls == []

    second_connection = FakeConnection()
    second_worker = _SignalWorker(
        FakeGio, FakeGLib, FakeProxy(second_connection), operation_timeout=0.2
    )
    second_worker.start()
    second_worker.subscribe(lambda _event: None)
    second_worker.unsubscribe(1)
    second_worker.close()
    second_worker.close()
    assert len(second_connection.unsubscribe_calls) == 3
