"""Repositorio de consultas snapshot de BlueZ."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from openbuds.domain.interfaces import IBluetoothRepository
from openbuds.domain.interfaces.observer import DeviceChangeCallback, Unsubscribe
from openbuds.domain.models import (
    AdapterInfo,
    BatteryLevel,
    DeviceChangeEvent,
    DeviceInfo,
    RSSIReading,
)
from openbuds.infrastructure.bluez.dbus_client import (
    IFACE_ADAPTER1,
    IFACE_BATTERY1,
    IFACE_DEVICE1,
    BlueZDBusClient,
)
from openbuds.infrastructure.bluez.dbus_protocol import ManagedObjects, SignalEvent
from openbuds.infrastructure.bluez.device_change_diff import diff_device_snapshots
from openbuds.infrastructure.bluez.object_mapper import (
    map_adapter,
    map_battery,
    map_device,
    map_rssi,
)

SignalCallback = Callable[[SignalEvent], None]
POLL_INTERVAL_DEFAULT_MS = 5000
_LOGGER = logging.getLogger(__name__)


class SnapshotClient(Protocol):
    """Cliente estructural de snapshots y señales de BlueZ."""

    def snapshot(self) -> ManagedObjects:
        """Devuelve el árbol actual de objetos administrados."""
        ...

    def subscribe(
        self,
        callback: SignalCallback,
        on_ready: Callable[[], None] | None = None,
        *,
        on_poll: Callable[[], None] | None = None,
        poll_interval_ms: int | None = None,
    ) -> int:
        """Registra una callback de señales y, opcionalmente, polling."""
        ...

    def unsubscribe(self, subscription_id: int) -> None:
        """Cancela una suscripción de señales."""
        ...


@dataclass
class _Subscriber:
    callback: DeviceChangeCallback
    active: bool = True
    in_flight: int = 0
    executing: dict[int, int] = field(default_factory=dict)


class BlueZRepository(IBluetoothRepository):
    """Repositorio de solo lectura basado en snapshots frescos de BlueZ."""

    def __init__(
        self,
        client: SnapshotClient | None = None,
        poll_interval_ms: int = POLL_INTERVAL_DEFAULT_MS,
    ) -> None:
        if type(poll_interval_ms) is not int or poll_interval_ms <= 0:
            raise ValueError("poll_interval_ms debe ser un entero positivo")
        self._client = client if client is not None else BlueZDBusClient()
        self._poll_interval_ms = poll_interval_ms
        self._condition = threading.Condition(threading.RLock())
        self._subscribers: dict[int, _Subscriber] = {}
        self._next_subscriber_id = 1
        self._cache: ManagedObjects | None = None
        self._low_subscription_id: int | None = None
        self._initializing = False
        self._initializing_thread_id: int | None = None
        self._initializing_subscriber_ids: set[int] = set()

    def list_adapters(self) -> list[AdapterInfo]:
        snapshot = self._client.snapshot()
        return [
            map_adapter(object_path, interfaces[IFACE_ADAPTER1])
            for object_path, interfaces in sorted(snapshot.items())
            if IFACE_ADAPTER1 in interfaces
        ]

    def list_devices(self, adapter_path: str | None = None) -> list[DeviceInfo]:
        snapshot = self._client.snapshot()
        devices = [
            (object_path, interfaces[IFACE_DEVICE1])
            for object_path, interfaces in sorted(snapshot.items())
            if IFACE_DEVICE1 in interfaces
        ]
        mapped = [map_device(object_path, props) for object_path, props in devices]
        if adapter_path is None:
            return mapped
        return [device for device in mapped if device.adapter_path == adapter_path]

    def get_device(self, device_path: str) -> DeviceInfo | None:
        snapshot = self._client.snapshot()
        interfaces = snapshot.get(device_path)
        if interfaces is None or IFACE_DEVICE1 not in interfaces:
            return None
        return map_device(device_path, interfaces[IFACE_DEVICE1])

    def get_battery(self, device_path: str) -> BatteryLevel | None:
        snapshot = self._client.snapshot()
        exact = snapshot.get(device_path)
        if exact is not None and IFACE_BATTERY1 in exact:
            return map_battery(exact[IFACE_BATTERY1])
        prefix = f"{device_path}/"
        for object_path, interfaces in sorted(snapshot.items()):
            if object_path.startswith(prefix) and IFACE_BATTERY1 in interfaces:
                return map_battery(interfaces[IFACE_BATTERY1])
        return None

    def get_rssi(self, device_path: str) -> RSSIReading | None:
        snapshot = self._client.snapshot()
        interfaces = snapshot.get(device_path)
        if interfaces is None or IFACE_DEVICE1 not in interfaces:
            return None
        props = interfaces[IFACE_DEVICE1]
        if "RSSI" not in props and "TxPower" not in props:
            return None
        return map_rssi(props)

    def subscribe_device_changes(self, callback: DeviceChangeCallback) -> Unsubscribe:
        current_thread_id = threading.get_ident()
        with self._condition:
            while self._initializing and self._initializing_thread_id != current_thread_id:
                self._condition.wait()
            subscriber_id = self._add_subscriber(callback)
            if self._low_subscription_id is not None:
                return self._make_unsubscribe(subscriber_id)
            if self._initializing:
                self._initializing_subscriber_ids.add(subscriber_id)
                return self._make_unsubscribe(subscriber_id)
            self._initializing = True
            self._initializing_thread_id = current_thread_id
            self._initializing_subscriber_ids = {subscriber_id}

        try:
            snapshot_a = self._client.snapshot()
            low_subscription_id = self._client.subscribe(
                self._handle_signal,
                on_ready=lambda: self._finish_initialization(snapshot_a),
                on_poll=self._handle_poll,
                poll_interval_ms=self._poll_interval_ms,
            )
        except Exception:
            self._abort_initialization()
            raise

        with self._condition:
            self._low_subscription_id = low_subscription_id
            self._initializing = False
            self._initializing_thread_id = None
            self._initializing_subscriber_ids.clear()
            self._condition.notify_all()
            should_unsubscribe = not self._subscribers
            if should_unsubscribe:
                self._low_subscription_id = None
                self._cache = None
        if should_unsubscribe:
            self._client.unsubscribe(low_subscription_id)
        return self._make_unsubscribe(subscriber_id)

    def _add_subscriber(self, callback: DeviceChangeCallback) -> int:
        subscriber_id = self._next_subscriber_id
        self._next_subscriber_id += 1
        self._subscribers[subscriber_id] = _Subscriber(callback)
        return subscriber_id

    def _make_unsubscribe(self, subscriber_id: int) -> Unsubscribe:
        called = False
        call_lock = threading.Lock()

        def unsubscribe() -> None:
            nonlocal called
            with call_lock:
                if called:
                    return
                called = True
            self._unsubscribe(subscriber_id)

        return unsubscribe

    def _unsubscribe(self, subscriber_id: int) -> None:
        low_subscription_id: int | None = None
        current_thread_id = threading.get_ident()
        with self._condition:
            subscriber = self._subscribers.pop(subscriber_id, None)
            if subscriber is None:
                return
            subscriber.active = False
            self._initializing_subscriber_ids.discard(subscriber_id)
            own_executions = subscriber.executing.get(current_thread_id, 0)
            while subscriber.in_flight - own_executions > 0:
                self._condition.wait()
            if (
                not self._subscribers
                and not self._initializing
                and self._low_subscription_id is not None
            ):
                low_subscription_id = self._low_subscription_id
                self._low_subscription_id = None
                self._cache = None
            self._condition.notify_all()
        if low_subscription_id is not None:
            self._client.unsubscribe(low_subscription_id)

    def _finish_initialization(self, snapshot_a: ManagedObjects) -> None:
        with self._condition:
            if not self._initializing:
                return
            self._initializing_thread_id = threading.get_ident()
        snapshot_b = self._client.snapshot()
        events = diff_device_snapshots(snapshot_a, snapshot_b)
        with self._condition:
            self._cache = snapshot_b
            recipients = tuple(self._subscribers.values())
        self._dispatch(events, recipients)

    def _abort_initialization(self) -> None:
        with self._condition:
            for subscriber_id in self._initializing_subscriber_ids:
                subscriber = self._subscribers.pop(subscriber_id, None)
                if subscriber is not None:
                    subscriber.active = False
            self._initializing_subscriber_ids.clear()
            self._cache = None
            self._initializing = False
            self._initializing_thread_id = None
            self._condition.notify_all()

    def _handle_poll(self) -> None:
        self._refresh_and_dispatch()

    def _handle_signal(self, _signal: SignalEvent) -> None:
        self._refresh_and_dispatch()

    def _refresh_and_dispatch(self) -> None:
        with self._condition:
            if not self._subscribers or self._cache is None:
                return
            previous = self._cache
        try:
            current = self._client.snapshot()
            events = diff_device_snapshots(previous, current)
        except Exception:
            _LOGGER.exception("BlueZ snapshot refresh failed")
            return
        with self._condition:
            if not self._subscribers or self._cache is not previous:
                return
            self._cache = current
            recipients = tuple(self._subscribers.values())
        self._dispatch(events, recipients)

    def _dispatch(
        self,
        events: tuple[DeviceChangeEvent, ...],
        recipients: tuple[_Subscriber, ...],
    ) -> None:
        for event in events:
            for subscriber in recipients:
                with self._condition:
                    if not subscriber.active:
                        continue
                    thread_id = threading.get_ident()
                    subscriber.in_flight += 1
                    subscriber.executing[thread_id] = subscriber.executing.get(thread_id, 0) + 1
                try:
                    subscriber.callback(event)
                except Exception:
                    _LOGGER.exception("BlueZ device change subscriber failed")
                finally:
                    with self._condition:
                        subscriber.in_flight -= 1
                        count = subscriber.executing[thread_id] - 1
                        if count:
                            subscriber.executing[thread_id] = count
                        else:
                            del subscriber.executing[thread_id]
                        self._condition.notify_all()
