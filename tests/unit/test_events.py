"""Tests del EventBus."""

from __future__ import annotations

from openbuds.core.events import Event, EventBus


class TestEventBus:
    def test_subscriber_receives_published_event(self) -> None:
        bus = EventBus()
        received: list[Event] = []
        bus.subscribe("device.connected", received.append)

        bus.publish(Event("device.connected", {"address": "AA:BB:CC"}))

        assert len(received) == 1
        assert received[0].name == "device.connected"
        assert received[0].payload == {"address": "AA:BB:CC"}

    def test_multiple_subscribers_all_receive(self) -> None:
        bus = EventBus()
        log_a: list[Event] = []
        log_b: list[Event] = []
        bus.subscribe("x", log_a.append)
        bus.subscribe("x", log_b.append)

        bus.publish(Event("x"))

        assert len(log_a) == 1
        assert len(log_b) == 1

    def test_unsubscribe_removes_callback(self) -> None:
        bus = EventBus()
        received: list[Event] = []
        cb = received.append
        bus.subscribe("y", cb)
        bus.unsubscribe("y", cb)

        bus.publish(Event("y"))

        assert received == []

    def test_publish_with_no_subscribers_is_noop(self) -> None:
        bus = EventBus()
        # No debe lanzar.
        bus.publish(Event("nonexistent"))

    def test_clear_removes_all_subscriptions(self) -> None:
        bus = EventBus()
        received: list[Event] = []
        bus.subscribe("z", received.append)
        bus.clear()

        bus.publish(Event("z"))

        assert received == []
