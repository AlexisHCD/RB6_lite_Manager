"""RED tests for BlueZRepository signal dispatch."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable

import pytest

from openbuds.core.errors import BluetoothError
from openbuds.domain.enums import DeviceChangeKind
from openbuds.domain.models import DeviceChangeEvent
from openbuds.infrastructure.bluez.bluez_repository import BlueZRepository
from openbuds.infrastructure.bluez.dbus_protocol import ManagedObjects, SignalEvent

Callback = Callable[[DeviceChangeEvent], None]


class FakeSignalClient:
    """Deterministic snapshot and low-level signal client, without GI."""

    def __init__(
        self,
        snapshots: Iterable[ManagedObjects | BaseException],
        *,
        subscribe_error: BaseException | None = None,
        on_ready_blocked: bool = False,
        on_ready_error: BaseException | None = None,
        on_ready_in_worker_thread: bool = False,
    ) -> None:
        self._snapshots = iter(snapshots)
        self.subscribe_error = subscribe_error
        self.on_ready_blocked = on_ready_blocked
        self.on_ready_error = on_ready_error
        self.on_ready_in_worker_thread = on_ready_in_worker_thread
        self.on_ready_entered = threading.Event()
        self.on_ready_release = threading.Event()
        self.on_ready_thread_ids: list[int] = []
        self._on_ready_workers: list[threading.Thread] = []
        self.snapshot_calls = 0
        self.low_callbacks: list[Callable[[SignalEvent], None]] = []
        self.active_low_callbacks: dict[int, Callable[[SignalEvent], None]] = {}
        self.subscribe_history: dict[
            int,
            tuple[
                Callable[[SignalEvent], None],
                Callable[[], None] | None,
                Callable[[], None] | None,
                int | None,
            ],
        ] = {}
        self.active_poll_callbacks: dict[int, Callable[[], None]] = {}
        self.subscribe_ids: list[int] = []
        self.unsubscribe_ids: list[int] = []
        self.close_calls = 0
        self._next_id = 1

    def snapshot(self) -> ManagedObjects:
        self.snapshot_calls += 1
        value = next(self._snapshots)
        if isinstance(value, BaseException):
            raise value
        return value

    def subscribe(
        self,
        callback: Callable[[SignalEvent], None],
        on_ready: Callable[[], None] | None = None,
        *,
        on_poll: Callable[[], None] | None = None,
        poll_interval_ms: int | None = None,
    ) -> int:
        if self.subscribe_error is not None:
            raise self.subscribe_error
        subscription_id = self._next_id
        self._next_id += 1
        self.low_callbacks.append(callback)
        self.active_low_callbacks[subscription_id] = callback
        self.subscribe_history[subscription_id] = (
            callback,
            on_ready,
            on_poll,
            poll_interval_ms,
        )
        if on_poll is not None:
            self.active_poll_callbacks[subscription_id] = on_poll
        self.subscribe_ids.append(subscription_id)
        try:
            if on_ready is not None:
                self.on_ready_entered.set()
                if self.on_ready_blocked and not self.on_ready_release.wait(1):
                    raise AssertionError("on_ready was not released")
                if self.on_ready_error is not None:
                    raise self.on_ready_error
                if self.on_ready_in_worker_thread:
                    result: list[object] = []
                    error: list[BaseException] = []

                    def run_on_ready() -> None:
                        self.on_ready_thread_ids.append(threading.get_ident())
                        try:
                            on_ready()
                        except BaseException as exception:
                            error.append(exception)
                        else:
                            result.append(None)

                    worker = threading.Thread(target=run_on_ready, daemon=True)
                    self._on_ready_workers.append(worker)
                    worker.start()
                    worker.join(0.25)
                    if worker.is_alive():
                        raise AssertionError("on_ready worker did not finish")
                    if error:
                        raise error[0]
                    assert result == [None]
                else:
                    on_ready()
        except BaseException:
            self.unsubscribe(subscription_id)
            raise
        return subscription_id

    def cleanup_on_ready_workers(self) -> None:
        """Join workers after repository rollback releases a blocked hook."""
        for worker in self._on_ready_workers:
            worker.join(1)
            assert not worker.is_alive(), "on_ready worker remained blocked"

    def unsubscribe(self, subscription_id: int) -> None:
        self.unsubscribe_ids.append(subscription_id)
        self.active_low_callbacks.pop(subscription_id, None)
        self.active_poll_callbacks.pop(subscription_id, None)

    def emit(self) -> None:
        event = SignalEvent(
            "org.freedesktop.DBus.ObjectManager",
            "InterfacesAdded",
            "/org/bluez/hci0/dev_A",
        )
        for callback in tuple(self.active_low_callbacks.values()):
            callback(event)

    def fire_poll(self) -> None:
        """Run active polling callbacks synchronously for deterministic tests."""
        for callback in tuple(self.active_poll_callbacks.values()):
            callback()

    def close(self) -> None:
        self.close_calls += 1


DEVICE = "/org/bluez/hci0/dev_A"
IFACE = "org.bluez.Device1"


def snapshot(
    *,
    name: str = "buds",
    connected: bool = False,
    paired: bool = False,
    trusted: bool = False,
    battery: int | None = None,
    rssi: int | None = None,
) -> ManagedObjects:
    interfaces: dict[str, dict[str, object]] = {
        IFACE: {
            "Address": "AA:BB:CC:DD:EE:FF",
            "Adapter": "/org/bluez/hci0",
            "Name": name,
            "Connected": connected,
            "Paired": paired,
            "Trusted": trusted,
        }
    }
    if rssi is not None:
        interfaces[IFACE]["RSSI"] = rssi
    if battery is not None:
        interfaces["org.bluez.Battery1"] = {"Percentage": battery}
    return {DEVICE: interfaces}


def snapshot_with_devices(*paths: str) -> ManagedObjects:
    return {
        path: {
            IFACE: {
                "Address": path.rsplit("_", 1)[-1],
                "Adapter": "/org/bluez/hci0",
            }
        }
        for path in paths
    }


def kinds(events: list[DeviceChangeEvent]) -> list[DeviceChangeKind]:
    return [event.kind for event in events]


def test_first_subscribe_snapshot_a_low_subscribe_on_ready_snapshot_b_equal_no_replay() -> None:
    client = FakeSignalClient([snapshot(), snapshot()])
    events: list[DeviceChangeEvent] = []

    BlueZRepository(client).subscribe_device_changes(events.append)

    assert events == []
    assert client.snapshot_calls == 2
    assert len(client.low_callbacks) == 1


def test_change_a_to_b_is_dispatched_before_subscribe_returns() -> None:
    client = FakeSignalClient([snapshot(), snapshot(name="new")])
    events: list[DeviceChangeEvent] = []

    BlueZRepository(client).subscribe_device_changes(events.append)

    assert len(events) == 1
    assert events[0].kind is DeviceChangeKind.UPDATED
    assert events[0].current is not None and events[0].current.name == "new"


def test_later_signal_refreshes_snapshot_c_and_diffs_b_to_c() -> None:
    client = FakeSignalClient([snapshot(), snapshot(), snapshot(name="later")])
    events: list[DeviceChangeEvent] = []
    BlueZRepository(client).subscribe_device_changes(events.append)

    client.emit()

    assert kinds(events) == [DeviceChangeKind.UPDATED]
    assert events[0].current is not None and events[0].current.name == "later"


def test_late_subscriber_gets_no_replay_and_one_low_subscription_fans_out_in_order() -> None:
    client = FakeSignalClient([snapshot(), snapshot(), snapshot(name="c")])
    first: list[DeviceChangeEvent] = []
    second: list[DeviceChangeEvent] = []
    repository = BlueZRepository(client)
    repository.subscribe_device_changes(first.append)
    repository.subscribe_device_changes(second.append)
    client.emit()

    assert first == second
    assert len(first) == 1
    assert len(client.low_callbacks) == 1


def test_same_callback_twice_is_independent_and_one_unsubscribe_leaves_other() -> None:
    client = FakeSignalClient([snapshot(), snapshot(), snapshot(name="c")])
    events: list[DeviceChangeEvent] = []
    repository = BlueZRepository(client)
    unsubscribe_one = repository.subscribe_device_changes(events.append)
    unsubscribe_two = repository.subscribe_device_changes(events.append)

    unsubscribe_one()
    client.emit()

    assert len(events) == 1
    unsubscribe_two()
    assert client.unsubscribe_ids == [client.subscribe_ids[0]]


def test_refresh_error_keeps_cache_and_next_successful_signal_diffs_b_to_d() -> None:
    error = BluetoothError("refresh")
    client = FakeSignalClient([snapshot(), snapshot(name="b"), error, snapshot(name="d")])
    events: list[DeviceChangeEvent] = []
    repository = BlueZRepository(client)
    repository.subscribe_device_changes(events.append)
    client.emit()
    assert len(events) == 1

    client.emit()

    assert len(events) == 2
    assert events[-1].previous == events[0].current
    assert events[-1].current is not None and events[-1].current.name == "d"


def test_mapper_error_keeps_cache_without_partial_events() -> None:
    invalid: ManagedObjects = {DEVICE: {IFACE: {"Address": "bad"}}}
    client = FakeSignalClient([snapshot(), snapshot(name="b"), invalid, snapshot(name="d")])
    events: list[DeviceChangeEvent] = []
    repository = BlueZRepository(client)
    repository.subscribe_device_changes(events.append)
    client.emit()
    client.emit()

    assert len(events) == 2
    assert events[-1].previous == events[0].current


def test_callback_error_does_not_escape_and_next_callback_receives_event() -> None:
    client = FakeSignalClient([snapshot(), snapshot(), snapshot(name="b")])
    received: list[DeviceChangeEvent] = []
    repository = BlueZRepository(client)
    repository.subscribe_device_changes(lambda _event: (_ for _ in ()).throw(RuntimeError("user")))
    repository.subscribe_device_changes(received.append)

    client.emit()

    assert len(received) == 1


def test_unsubscribe_is_idempotent_and_new_cycle_uses_new_low_id_and_cache() -> None:
    client = FakeSignalClient(
        [
            snapshot(),
            snapshot(),
            snapshot(name="new-a"),
            snapshot(name="new-a"),
            snapshot(name="new-b"),
        ]
    )
    events: list[DeviceChangeEvent] = []
    repository = BlueZRepository(client)
    unsubscribe = repository.subscribe_device_changes(events.append)
    unsubscribe()
    unsubscribe()
    assert client.unsubscribe_ids == [1]

    repository.subscribe_device_changes(events.append)
    assert client.subscribe_ids == [1, 2]
    client.emit()
    assert len(events) == 1


def test_self_unsubscribe_from_signal_callback_has_no_deadlock_or_future_events() -> None:
    client = FakeSignalClient([snapshot(), snapshot(), snapshot(name="b")])
    repository = BlueZRepository(client)
    events: list[DeviceChangeEvent] = []
    holder: list[Callable[[], None]] = []

    def callback(event: DeviceChangeEvent) -> None:
        events.append(event)
        holder[0]()

    holder.append(repository.subscribe_device_changes(callback))
    client.emit()
    client.emit()

    assert len(events) == 1
    assert client.unsubscribe_ids == [1]


def test_external_unsubscribe_waits_for_blocked_callback_and_then_stops_future_events() -> None:
    client = FakeSignalClient([snapshot(), snapshot(), snapshot(name="b")])
    entered = threading.Event()
    release = threading.Event()
    events: list[DeviceChangeEvent] = []

    def callback(event: DeviceChangeEvent) -> None:
        events.append(event)
        entered.set()
        assert release.wait(1)

    repository = BlueZRepository(client)
    unsubscribe = repository.subscribe_device_changes(callback)
    emit_thread = threading.Thread(target=client.emit)
    emit_thread.start()
    assert entered.wait(1)
    unsubscribe_thread = threading.Thread(target=unsubscribe)
    unsubscribe_thread.start()
    assert unsubscribe_thread.is_alive()
    release.set()
    emit_thread.join(1)
    unsubscribe_thread.join(1)
    client.emit()

    assert not unsubscribe_thread.is_alive()
    assert len(events) == 1


def test_second_concurrent_subscriber_waits_initialization_and_gets_no_replay() -> None:
    client = FakeSignalClient(
        [snapshot(), snapshot(), snapshot(name="future")], on_ready_blocked=True
    )
    repository = BlueZRepository(client)
    first: list[DeviceChangeEvent] = []
    second: list[DeviceChangeEvent] = []
    first_thread = threading.Thread(
        target=lambda: repository.subscribe_device_changes(first.append)
    )
    first_thread.start()
    assert client.on_ready_entered.wait(1)
    second_thread = threading.Thread(
        target=lambda: repository.subscribe_device_changes(second.append)
    )
    second_thread.start()
    assert second_thread.is_alive()
    client.on_ready_release.set()
    first_thread.join(1)
    second_thread.join(1)
    client.emit()

    assert first == second
    assert len(first) == 1


def test_reentrant_subscriber_from_callback_does_not_receive_current_event_but_gets_future() -> (
    None
):
    client = FakeSignalClient([snapshot(), snapshot(name="b"), snapshot(name="c")])
    repository = BlueZRepository(client)
    first: list[DeviceChangeEvent] = []
    second: list[DeviceChangeEvent] = []
    registered = False

    def callback(event: DeviceChangeEvent) -> None:
        nonlocal registered
        first.append(event)
        if not registered:
            registered = True
            repository.subscribe_device_changes(second.append)

    repository.subscribe_device_changes(callback)
    client.emit()

    assert len(first) == 2
    assert len(second) == 1


def test_worker_on_ready_reentrant_subscriber_does_not_deadlock_or_replay() -> None:
    client = FakeSignalClient(
        [
            snapshot(),
            snapshot(name="b"),
            snapshot(name="c"),
            snapshot(name="c"),
        ],
        on_ready_in_worker_thread=True,
    )
    repository = BlueZRepository(client)
    first: list[DeviceChangeEvent] = []
    second: list[DeviceChangeEvent] = []
    caller_thread_id = threading.get_ident()
    callback_thread_ids: list[int] = []
    registered = False

    def callback(event: DeviceChangeEvent) -> None:
        nonlocal registered
        first.append(event)
        callback_thread_ids.append(threading.get_ident())
        if not registered:
            registered = True
            repository.subscribe_device_changes(second.append)

    try:
        repository.subscribe_device_changes(callback)
        assert first[0].current is not None
        assert first[0].current.name == "b"
        assert callback_thread_ids[0] != caller_thread_id
        assert second == []

        client.emit()
    finally:
        client.cleanup_on_ready_workers()

    assert len(first) == 2
    assert len(second) == 1
    assert first[-1].current is not None and first[-1].current.name == "c"
    assert second[0].current is not None and second[0].current.name == "c"


def test_initial_snapshot_error_does_not_low_subscribe_and_retry_works() -> None:
    client = FakeSignalClient([BluetoothError("initial"), snapshot(), snapshot(name="b")])
    repository = BlueZRepository(client)
    with pytest.raises(BluetoothError):
        repository.subscribe_device_changes(lambda _: None)

    repository.subscribe_device_changes(lambda _: None)
    assert client.subscribe_ids == [1]


def test_snapshot_b_or_on_ready_error_rolls_back_and_retry_works_without_events() -> None:
    client = FakeSignalClient(
        [snapshot(), BluetoothError("refresh"), snapshot(), snapshot(name="b")],
    )
    repository = BlueZRepository(client)
    with pytest.raises(BluetoothError):
        repository.subscribe_device_changes(lambda _: None)
    repository.subscribe_device_changes(lambda _: None)
    assert client.unsubscribe_ids == [1]


def test_low_subscribe_error_leaves_clean_state_and_retry_works() -> None:
    client = FakeSignalClient(
        [snapshot(), snapshot(), snapshot()], subscribe_error=BluetoothError("low")
    )
    repository = BlueZRepository(client)
    with pytest.raises(BluetoothError):
        repository.subscribe_device_changes(lambda _: None)
    client.subscribe_error = None
    repository.subscribe_device_changes(lambda _: None)
    assert client.subscribe_ids == [1]


def test_dispatch_preserves_removed_added_updated_order() -> None:
    old = snapshot_with_devices("/old", "/same")
    new = snapshot_with_devices("/added", "/same")
    new["/same"][IFACE]["Name"] = "changed"
    client = FakeSignalClient([old, old, new])
    events: list[DeviceChangeEvent] = []
    repository = BlueZRepository(client)
    repository.subscribe_device_changes(events.append)
    client.emit()

    assert kinds(events) == [
        DeviceChangeKind.REMOVED,
        DeviceChangeKind.ADDED,
        DeviceChangeKind.UPDATED,
    ]


def test_battery_and_rssi_only_changes_do_not_dispatch_user_event() -> None:
    a = snapshot(battery=10)
    b = snapshot(battery=20)
    b[DEVICE][IFACE]["RSSI"] = -50
    c = snapshot(battery=30)
    c[DEVICE][IFACE]["RSSI"] = -40
    client = FakeSignalClient([a, a, b, c])
    events: list[DeviceChangeEvent] = []
    repository = BlueZRepository(client)
    repository.subscribe_device_changes(events.append)
    client.emit()
    client.emit()

    assert events == []


def test_user_callbacks_can_reentrantly_subscribe_and_unsubscribe_without_repo_lock_deadlock() -> (
    None
):
    client = FakeSignalClient([snapshot(), snapshot(name="b"), snapshot(name="c")])
    repository = BlueZRepository(client)
    nested: list[DeviceChangeEvent] = []
    done = threading.Event()
    nested_unsubscribe: list[Callable[[], None]] = []

    def callback(_event: DeviceChangeEvent) -> None:
        unsubscribe = repository.subscribe_device_changes(nested.append)
        nested_unsubscribe.append(unsubscribe)
        unsubscribe()
        done.set()

    repository.subscribe_device_changes(callback)
    done.clear()
    thread = threading.Thread(target=client.emit)
    thread.start()
    assert done.wait(1)
    thread.join(1)
    assert not thread.is_alive()


def test_repository_never_closes_client() -> None:
    client = FakeSignalClient([snapshot(), snapshot()])
    unsubscribe = BlueZRepository(client).subscribe_device_changes(lambda _: None)
    unsubscribe()

    assert client.close_calls == 0


def test_first_low_subscription_receives_default_poll_options() -> None:
    client = FakeSignalClient([snapshot(), snapshot()])
    repository = BlueZRepository(client)

    repository.subscribe_device_changes(lambda _: None)

    _, _, on_poll, interval = client.subscribe_history[client.subscribe_ids[0]]
    assert callable(on_poll)
    assert interval == 5000


def test_injected_poll_interval_is_forwarded_exactly() -> None:
    client = FakeSignalClient([snapshot(), snapshot()])
    repository = BlueZRepository(client, poll_interval_ms=1234)

    repository.subscribe_device_changes(lambda _: None)

    _, _, on_poll, interval = client.subscribe_history[client.subscribe_ids[0]]
    assert callable(on_poll)
    assert interval == 1234


@pytest.mark.parametrize("poll_interval_ms", [0, -1, "1234", True])
def test_invalid_poll_interval_is_rejected_before_client_use(
    poll_interval_ms: object,
) -> None:
    client = FakeSignalClient([snapshot()])

    with pytest.raises(ValueError):
        BlueZRepository(client, poll_interval_ms=poll_interval_ms)  # type: ignore[arg-type]

    assert client.snapshot_calls == 0
    assert client.subscribe_ids == []


def test_late_subscriber_does_not_create_another_poll_timer() -> None:
    client = FakeSignalClient([snapshot(), snapshot()])
    repository = BlueZRepository(client)

    repository.subscribe_device_changes(lambda _: None)
    repository.subscribe_device_changes(lambda _: None)

    assert client.subscribe_ids == [1]
    assert list(client.active_poll_callbacks) == [1]
    assert len(client.subscribe_history) == 1


def test_poll_dispatches_connected_paired_and_trusted_changes() -> None:
    initial = snapshot()
    changed = snapshot(connected=True, paired=True, trusted=True)
    client = FakeSignalClient([initial, initial, changed])
    events: list[DeviceChangeEvent] = []
    repository = BlueZRepository(client)
    repository.subscribe_device_changes(events.append)

    client.fire_poll()

    assert kinds(events) == [DeviceChangeKind.UPDATED]
    event = events[0]
    assert event.current is not None and event.previous is not None
    assert event.current.connected is True
    assert event.current.paired is True
    assert event.current.trusted is True
    assert event.previous.connected is False
    assert event.previous.paired is False
    assert event.previous.trusted is False


def test_signal_and_poll_share_cache_without_duplicate_events() -> None:
    initial = snapshot()
    changed_b = snapshot(name="b")
    changed_c = snapshot(name="c")
    client = FakeSignalClient([initial, initial, changed_b, changed_b, changed_c, changed_c])
    events: list[DeviceChangeEvent] = []
    repository = BlueZRepository(client)
    repository.subscribe_device_changes(events.append)

    client.fire_poll()
    client.emit()
    client.emit()
    client.fire_poll()

    assert [event.current.name for event in events if event.current is not None] == ["b", "c"]


def test_poll_snapshot_error_preserves_cache_for_next_success() -> None:
    initial = snapshot()
    changed = snapshot(name="b")
    client = FakeSignalClient([initial, initial, BluetoothError("poll"), changed])
    events: list[DeviceChangeEvent] = []
    repository = BlueZRepository(client)
    repository.subscribe_device_changes(events.append)

    client.fire_poll()
    assert events == []
    client.fire_poll()

    assert len(events) == 1
    assert events[0].previous is not None and events[0].previous.name == "buds"
    assert events[0].current is not None and events[0].current.name == "b"


def test_poll_mapper_error_preserves_cache_without_partial_events() -> None:
    invalid: ManagedObjects = {DEVICE: {IFACE: {"Address": "bad"}}}
    client = FakeSignalClient([snapshot(), snapshot(), invalid, snapshot(name="d")])
    events: list[DeviceChangeEvent] = []
    repository = BlueZRepository(client)
    repository.subscribe_device_changes(events.append)

    client.fire_poll()
    assert events == []
    client.fire_poll()

    assert len(events) == 1
    assert events[0].previous is not None and events[0].previous.name == "buds"


def test_poll_battery_and_rssi_only_changes_do_not_dispatch_user_event() -> None:
    initial = snapshot(battery=10, rssi=-50)
    changed = snapshot(battery=20, rssi=-40)
    client = FakeSignalClient([initial, initial, changed])
    events: list[DeviceChangeEvent] = []
    repository = BlueZRepository(client)
    repository.subscribe_device_changes(events.append)

    client.fire_poll()

    assert events == []


def test_poll_callback_error_does_not_block_next_subscriber() -> None:
    client = FakeSignalClient([snapshot(), snapshot(), snapshot(name="b")])
    received: list[DeviceChangeEvent] = []
    repository = BlueZRepository(client)
    repository.subscribe_device_changes(lambda _event: (_ for _ in ()).throw(RuntimeError("user")))
    repository.subscribe_device_changes(received.append)

    client.fire_poll()

    assert len(received) == 1


def test_self_unsubscribe_from_poll_callback_stops_future_polls() -> None:
    client = FakeSignalClient([snapshot(), snapshot(), snapshot(name="b")])
    repository = BlueZRepository(client)
    events: list[DeviceChangeEvent] = []
    holder: list[Callable[[], None]] = []

    def callback(event: DeviceChangeEvent) -> None:
        events.append(event)
        holder[0]()

    holder.append(repository.subscribe_device_changes(callback))
    client.fire_poll()
    client.fire_poll()

    assert len(events) == 1
    assert client.unsubscribe_ids == [1]
    assert client.snapshot_calls == 3
    assert client.active_poll_callbacks == {}


def test_external_unsubscribe_waits_for_blocked_poll_callback() -> None:
    client = FakeSignalClient([snapshot(), snapshot(), snapshot(name="b")])
    entered = threading.Event()
    release = threading.Event()
    events: list[DeviceChangeEvent] = []

    def callback(event: DeviceChangeEvent) -> None:
        events.append(event)
        entered.set()
        assert release.wait(1)

    repository = BlueZRepository(client)
    unsubscribe = repository.subscribe_device_changes(callback)
    poll_thread = threading.Thread(target=client.fire_poll)
    poll_thread.start()
    assert entered.wait(1)
    unsubscribe_thread = threading.Thread(target=unsubscribe)
    unsubscribe_thread.start()
    assert unsubscribe_thread.is_alive()
    release.set()
    poll_thread.join(1)
    unsubscribe_thread.join(1)
    client.fire_poll()

    assert not unsubscribe_thread.is_alive()
    assert len(events) == 1
    assert client.snapshot_calls == 3
    assert client.unsubscribe_ids == [1]


def test_last_unsubscribe_cancels_poll_and_new_cycle_gets_new_cache() -> None:
    first = snapshot(name="first")
    second = snapshot(name="second")
    changed = snapshot(name="changed")
    client = FakeSignalClient([first, first, second, second, changed])
    events: list[DeviceChangeEvent] = []
    repository = BlueZRepository(client)

    unsubscribe = repository.subscribe_device_changes(events.append)
    unsubscribe()
    unsubscribe()
    assert client.active_poll_callbacks == {}

    repository.subscribe_device_changes(events.append)
    assert client.subscribe_ids == [1, 2]
    assert list(client.active_poll_callbacks) == [2]
    client.fire_poll()

    assert len(events) == 1
    assert events[0].previous is not None and events[0].previous.name == "second"
    assert client.unsubscribe_ids == [1]


def test_signal_and_poll_use_the_same_dispatch_behavior() -> None:
    initial = snapshot()
    changed = snapshot(name="changed")
    poll_client = FakeSignalClient([initial, initial, changed])
    signal_client = FakeSignalClient([initial, initial, changed])
    poll_events: list[DeviceChangeEvent] = []
    signal_events: list[DeviceChangeEvent] = []
    poll_repository = BlueZRepository(poll_client)
    signal_repository = BlueZRepository(signal_client)
    poll_repository.subscribe_device_changes(poll_events.append)
    signal_repository.subscribe_device_changes(signal_events.append)

    poll_client.fire_poll()
    signal_client.emit()

    assert len(poll_events) == 1
    assert signal_events == poll_events
