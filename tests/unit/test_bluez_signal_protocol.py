"""TDD RED contract for GioDBusProtocol signal-worker wiring."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

import pytest

from openbuds.core.errors import BluetoothError
from openbuds.infrastructure.bluez.dbus_protocol import (
    GioDBusProtocol,
    ManagedObjects,
    SignalEvent,
)

SNAPSHOT: ManagedObjects = {
    "/org/bluez/hci0": {
        "org.bluez.Adapter1": {"Address": "AA:BB:CC:DD:EE:FF"},
    }
}


class FakeGLibError(Exception):
    pass


class FakeGLib:
    Error = FakeGLibError


class FakeReply:
    def __init__(self, value: object) -> None:
        self.value = value

    def get_type_string(self) -> str:
        return "(a{oa{sa{sv}}})"

    def unpack(self) -> object:
        return self.value


class FakeConnection:
    def __init__(self) -> None:
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


class FakeProxy:
    def __init__(self) -> None:
        self.connection = FakeConnection()
        self.close_calls = 0
        self.snapshot_calls = 0

    def call_sync(self, *_args: object) -> FakeReply:
        self.snapshot_calls += 1
        return FakeReply((SNAPSHOT,))

    def get_connection(self) -> FakeConnection:
        return self.connection

    def close(self) -> None:
        self.close_calls += 1


class FakeGio:
    class BusType:
        SYSTEM = "system"

    class DBusProxyFlags:
        DO_NOT_AUTO_START = "no-auto-start-proxy"

    class DBusCallFlags:
        NO_AUTO_START = "no-auto-start-call"

    def __init__(self, proxy: FakeProxy) -> None:
        self.proxy = proxy
        self.DBusProxy = self

    def new_for_bus_sync(self, *_args: object) -> FakeProxy:
        return self.proxy


class FakeWorker:
    def __init__(
        self,
        *,
        start_error: BaseException | None = None,
        subscribe_error: BaseException | None = None,
    ) -> None:
        self.start_error = start_error
        self.subscribe_error = subscribe_error
        self.start_calls = 0
        self.subscribe_calls: list[Callable[[SignalEvent], None]] = []
        self.on_ready_calls: list[Callable[[], None] | None] = []
        self.on_poll_calls: list[Callable[[], None] | None] = []
        self.intervals: list[int | None] = []
        self.unsubscribe_calls: list[int] = []
        self.close_calls = 0
        self._closed = False
        self._next_id = 1
        self._active_ids: set[int] = set()

    @property
    def is_closed(self) -> bool:
        return self._closed

    def start(self) -> None:
        self.start_calls += 1
        if self.start_error is not None:
            raise self.start_error

    def subscribe(
        self,
        callback: Callable[[SignalEvent], None],
        on_ready: Callable[[], None] | None = None,
        *,
        on_poll: Callable[[], None] | None = None,
        poll_interval_ms: int | None = None,
    ) -> int:
        self.subscribe_calls.append(callback)
        self.on_ready_calls.append(on_ready)
        self.on_poll_calls.append(on_poll)
        self.intervals.append(poll_interval_ms)
        if self.subscribe_error is not None:
            raise self.subscribe_error
        subscription_id = self._next_id
        self._next_id += 1
        self._active_ids.add(subscription_id)
        if on_ready is not None:
            on_ready()
        return subscription_id

    def unsubscribe(self, subscription_id: int) -> None:
        self.unsubscribe_calls.append(subscription_id)
        self._active_ids.discard(subscription_id)
        if not self._active_ids:
            self._closed = True

    def close(self) -> None:
        self.close_calls += 1
        self._closed = True


class WorkerFactory:
    def __init__(self, workers: list[FakeWorker]) -> None:
        self.workers = workers
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> FakeWorker:
        self.calls.append((args, kwargs))
        return self.workers.pop(0)


class FalseyWorkerFactory(WorkerFactory):
    def __bool__(self) -> bool:
        return False


class BlockingStartWorker(FakeWorker):
    def __init__(self) -> None:
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()

    def start(self) -> None:
        self.entered.set()
        self.release.wait()
        super().start()


@pytest.fixture
def gio_and_proxy() -> tuple[FakeGio, FakeProxy]:
    proxy = FakeProxy()
    return FakeGio(proxy), proxy


def make_loader(gio: FakeGio) -> Callable[[], tuple[FakeGio, type[FakeGLib]]]:
    def loader() -> tuple[FakeGio, type[FakeGLib]]:
        return gio, FakeGLib

    return loader


def make_protocol(
    gio: FakeGio,
    worker_factory: WorkerFactory,
) -> GioDBusProtocol:
    return GioDBusProtocol(loader=make_loader(gio), worker_factory=worker_factory)


def test_construct_snapshot_and_close_are_lazy_about_signal_worker(
    gio_and_proxy: tuple[FakeGio, FakeProxy],
) -> None:
    gio, proxy = gio_and_proxy
    factory = WorkerFactory([FakeWorker()])

    protocol = make_protocol(gio, factory)

    assert protocol.get_managed_objects() == SNAPSHOT
    assert factory.calls == []
    protocol.close()
    assert factory.calls == []
    assert proxy.close_calls == 0
    assert proxy.connection.close_calls == 0


def test_first_subscribe_creates_and_starts_once_then_delegates_callbacks_and_ids(
    gio_and_proxy: tuple[FakeGio, FakeProxy],
) -> None:
    gio, _proxy = gio_and_proxy
    worker = FakeWorker()
    factory = WorkerFactory([worker])
    protocol = make_protocol(gio, factory)

    def first_callback(_event: SignalEvent) -> None:
        pass

    def second_callback(_event: SignalEvent) -> None:
        pass

    first_id = protocol.subscribe(first_callback)
    second_id = protocol.subscribe(second_callback)

    assert len(factory.calls) == 1
    assert worker.start_calls == 1
    assert worker.subscribe_calls == [first_callback, second_callback]
    assert (first_id, second_id) == (1, 2)


def test_subscribe_forwards_on_ready_to_worker_and_fake_executes_it(
    gio_and_proxy: tuple[FakeGio, FakeProxy],
) -> None:
    gio, _proxy = gio_and_proxy
    worker = FakeWorker()
    protocol = make_protocol(gio, WorkerFactory([worker]))
    calls: list[str] = []

    assert protocol.subscribe(lambda _event: None, on_ready=lambda: calls.append("ready")) == 1

    assert calls == ["ready"]
    assert worker.on_ready_calls[0] is not None


def test_protocol_forwards_poll_callback_and_exact_interval_to_worker(
    gio_and_proxy: tuple[FakeGio, FakeProxy],
) -> None:
    gio, _proxy = gio_and_proxy
    worker = FakeWorker()
    protocol = make_protocol(gio, WorkerFactory([worker]))

    def on_poll() -> None:
        pass

    assert protocol.subscribe(lambda _event: None, on_poll=on_poll, poll_interval_ms=137) == 1

    assert worker.on_poll_calls == [on_poll]
    assert worker.intervals == [137]


def test_protocol_rejects_invalid_polling_before_creating_worker(
    gio_and_proxy: tuple[FakeGio, FakeProxy],
) -> None:
    gio, _proxy = gio_and_proxy
    factory = WorkerFactory([FakeWorker()])
    protocol = make_protocol(gio, factory)

    with pytest.raises(ValueError, match="juntos"):
        protocol.subscribe(lambda _event: None, on_poll=lambda: None)

    assert factory.calls == []


def test_invalid_polling_does_not_close_existing_worker_or_subscriptions(
    gio_and_proxy: tuple[FakeGio, FakeProxy],
) -> None:
    gio, _proxy = gio_and_proxy
    worker = FakeWorker()
    factory = WorkerFactory([worker])
    protocol = make_protocol(gio, factory)
    first_id = protocol.subscribe(lambda _event: None)

    with pytest.raises(ValueError, match="juntos"):
        protocol.subscribe(lambda _event: None, poll_interval_ms=100)

    second_id = protocol.subscribe(lambda _event: None)
    assert (first_id, second_id) == (1, 2)
    assert worker.close_calls == 0
    assert len(factory.calls) == 1


def test_on_ready_failure_cleans_worker_reference_and_next_subscribe_creates_new_worker(
    gio_and_proxy: tuple[FakeGio, FakeProxy],
) -> None:
    gio, _proxy = gio_and_proxy
    failed_worker = FakeWorker()
    working_worker = FakeWorker()
    protocol = make_protocol(gio, WorkerFactory([failed_worker, working_worker]))

    def on_ready() -> None:
        raise RuntimeError("ready hook failed")

    with pytest.raises(BluetoothError, match="registrar") as raised:
        protocol.subscribe(lambda _event: None, on_ready=on_ready)

    assert isinstance(raised.value.__cause__, RuntimeError)
    assert failed_worker.is_closed
    assert protocol.subscribe(lambda _event: None) == 1
    assert working_worker.start_calls == 1


def test_worker_subscribe_failure_cleans_worker_reference_and_next_subscribe_recreates_it(
    gio_and_proxy: tuple[FakeGio, FakeProxy],
) -> None:
    gio, _proxy = gio_and_proxy
    failed_worker = FakeWorker(subscribe_error=RuntimeError("subscribe failed"))
    working_worker = FakeWorker()
    protocol = make_protocol(gio, WorkerFactory([failed_worker, working_worker]))

    with pytest.raises(BluetoothError, match="registrar"):
        protocol.subscribe(lambda _event: None)

    assert failed_worker.is_closed
    assert protocol.subscribe(lambda _event: None) == 1
    assert working_worker.start_calls == 1


def test_unsubscribe_non_last_keeps_worker_and_last_closes_it_then_next_subscribe_recreates(
    gio_and_proxy: tuple[FakeGio, FakeProxy],
) -> None:
    gio, _proxy = gio_and_proxy
    first_worker = FakeWorker()
    second_worker = FakeWorker()
    factory = WorkerFactory([first_worker, second_worker])
    protocol = make_protocol(gio, factory)

    first_id = protocol.subscribe(lambda _event: None)
    second_id = protocol.subscribe(lambda _event: None)
    protocol.unsubscribe(first_id)
    assert first_worker.close_calls == 0
    protocol.unsubscribe(second_id)
    assert first_worker.is_closed

    protocol.subscribe(lambda _event: None)
    assert len(factory.calls) == 2
    assert second_worker.start_calls == 1


def test_start_failure_cleans_reference_and_next_subscribe_uses_new_worker(
    gio_and_proxy: tuple[FakeGio, FakeProxy],
) -> None:
    gio, _proxy = gio_and_proxy
    failed_worker = FakeWorker(start_error=RuntimeError("start failed"))
    working_worker = FakeWorker()
    factory = WorkerFactory([failed_worker, working_worker])
    protocol = make_protocol(gio, factory)

    with pytest.raises(BluetoothError):
        protocol.subscribe(lambda _event: None)

    subscription_id = protocol.subscribe(lambda _event: None)
    assert subscription_id == 1
    assert len(factory.calls) == 2
    assert working_worker.start_calls == 1


def test_close_is_idempotent_closes_worker_once_without_closing_gio_objects(
    gio_and_proxy: tuple[FakeGio, FakeProxy],
) -> None:
    gio, proxy = gio_and_proxy
    worker = FakeWorker()
    protocol = make_protocol(gio, WorkerFactory([worker]))
    protocol.subscribe(lambda _event: None)

    protocol.close()
    protocol.close()

    assert worker.close_calls == 1
    assert proxy.close_calls == 0
    assert proxy.connection.close_calls == 0


def test_subscribe_after_protocol_close_fails_immediately_without_creating_worker(
    gio_and_proxy: tuple[FakeGio, FakeProxy],
) -> None:
    gio, _proxy = gio_and_proxy
    factory = WorkerFactory([FakeWorker()])
    protocol = make_protocol(gio, factory)
    protocol.close()

    with pytest.raises(BluetoothError):
        protocol.subscribe(lambda _event: None)

    assert factory.calls == []


def test_context_manager_closes_protocol_when_body_raises(
    gio_and_proxy: tuple[FakeGio, FakeProxy],
) -> None:
    gio, _proxy = gio_and_proxy
    worker = FakeWorker()
    factory = WorkerFactory([worker])
    protocol = make_protocol(gio, factory)
    protocol.subscribe(lambda _event: None)

    with pytest.raises(RuntimeError, match="context failure"), protocol:
        raise RuntimeError("context failure")

    assert worker.close_calls == 1


def test_falsey_worker_factory_is_used_for_signal_subscription(
    gio_and_proxy: tuple[FakeGio, FakeProxy],
) -> None:
    gio, _proxy = gio_and_proxy
    worker = FakeWorker()
    factory = FalseyWorkerFactory([worker])
    protocol = make_protocol(gio, factory)

    subscription_id = protocol.subscribe(lambda _event: None)

    assert subscription_id == 1
    assert len(factory.calls) == 1
    assert worker.start_calls == 1
    assert len(worker.subscribe_calls) == 1


def test_close_during_worker_start_rejects_concurrent_subscription(
    gio_and_proxy: tuple[FakeGio, FakeProxy],
) -> None:
    gio, _proxy = gio_and_proxy
    worker = BlockingStartWorker()
    factory = WorkerFactory([worker])
    protocol = make_protocol(gio, factory)
    result: list[int] = []
    errors: list[BaseException] = []

    def subscribe() -> None:
        try:
            result.append(protocol.subscribe(lambda _event: None))
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=subscribe)
    thread.start()
    assert worker.entered.wait(1)

    protocol.close()
    assert worker.close_calls == 1

    worker.release.set()
    thread.join(1)

    assert not thread.is_alive()
    assert result == []
    assert len(errors) == 1
    assert isinstance(errors[0], BluetoothError)
    assert "cerrado" in str(errors[0])
    assert worker.subscribe_calls == []
