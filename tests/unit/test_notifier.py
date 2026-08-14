"""Unit tests for the privacy-safe desktop notification adapter."""

from __future__ import annotations

import logging

from openbuds.presentation.notifications.notifier import DesktopNotifier


class FakeVariant:
    """Record the requested GVariant signature and value."""

    def __init__(self, signature: str, value: object) -> None:
        self.signature = signature
        self.value = value


class FakeProxy:
    """Record calls made to the notification D-Bus proxy."""

    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[object, ...]] = []

    def call_sync(self, *args: object) -> None:
        self.calls.append(args)
        if self.error is not None:
            raise self.error


def test_notify_lazily_creates_proxy_and_uses_standard_notify_shape() -> None:
    proxy = FakeProxy()
    loaders = 0
    variants: list[FakeVariant] = []

    def load_proxy() -> FakeProxy:
        nonlocal loaders
        loaders += 1
        return proxy

    def make_variant(signature: str, value: object) -> FakeVariant:
        variant = FakeVariant(signature, value)
        variants.append(variant)
        return variant

    notifier = DesktopNotifier(proxy_loader=load_proxy, variant_factory=make_variant)

    assert loaders == 0
    notifier.notify("Estado\nconectado", "Buds 00:11:22:33:44:55 /org/bluez/hci0/dev_x")

    assert loaders == 1
    assert len(proxy.calls) == 1
    method, parameters, flags, timeout, cancellable = proxy.calls[0]
    assert method == "Notify"
    assert flags == 0
    assert timeout == -1
    assert cancellable is None
    assert isinstance(parameters, FakeVariant)
    assert variants[0] is parameters
    assert parameters.signature == "(susssasa{sv}i)"
    assert parameters.value == (
        "OpenBuds Manager",
        0,
        "",
        "Estado?conectado",
        "Buds <redacted> <redacted>",
        [],
        {},
        -1,
    )


def test_notify_reuses_proxy_for_best_effort_calls() -> None:
    proxy = FakeProxy()

    def load_proxy() -> FakeProxy:
        return proxy

    notifier = DesktopNotifier(proxy_loader=load_proxy, variant_factory=FakeVariant)

    notifier.notify("Una")
    notifier.notify("Dos")

    assert len(proxy.calls) == 2


def test_notify_redacts_non_bluez_object_path_from_variant_payload() -> None:
    proxy = FakeProxy()
    notifier = DesktopNotifier(proxy_loader=lambda: proxy, variant_factory=FakeVariant)
    raw_path = "/org/freedesktop/Notifications"

    notifier.notify("Conectado", f"Ruta {raw_path}")

    parameters = proxy.calls[0][1]
    assert isinstance(parameters, FakeVariant)
    assert isinstance(parameters.value, tuple)
    assert parameters.value[4] == "Ruta <redacted>"
    assert raw_path not in parameters.value[4]


def test_notify_redacts_hyphenated_mac_and_generic_object_paths_from_payload() -> None:
    proxy = FakeProxy()
    notifier = DesktopNotifier(proxy_loader=lambda: proxy, variant_factory=FakeVariant)
    mac = "AA-BB-CC-DD-EE-FF"
    io_path = "/io/example/object"
    xyz_path = "/xyz/example/object"

    notifier.notify("Conectado", f"Device {mac} {io_path} {xyz_path}")

    parameters = proxy.calls[0][1]
    assert isinstance(parameters, FakeVariant)
    assert isinstance(parameters.value, tuple)
    assert parameters.value[4] == "Device <redacted> <redacted> <redacted>"
    assert mac not in parameters.value[4]
    assert io_path not in parameters.value[4]
    assert xyz_path not in parameters.value[4]


def test_notify_redacts_long_object_path_before_truncating_field() -> None:
    proxy = FakeProxy()
    notifier = DesktopNotifier(proxy_loader=lambda: proxy, variant_factory=FakeVariant)
    prefix = "P" * 62
    raw_path = "/org/freedesktop/" + ("component/" * 19) + "component"

    notifier.notify("Conectado", f"{prefix} {raw_path}")

    parameters = proxy.calls[0][1]
    assert isinstance(parameters, FakeVariant)
    assert isinstance(parameters.value, tuple)
    assert parameters.value[4] == f"{prefix} <redacted>"
    assert len(parameters.value[4]) <= 80


def test_notify_swallows_proxy_failure_without_logging_raw_error(caplog) -> None:  # type: ignore[no-untyped-def]
    raw_error = "D-Bus failed for 00:11:22:33:44:55 /org/bluez/hci0/dev_x"
    proxy = FakeProxy(error=RuntimeError(raw_error))
    notifier = DesktopNotifier(proxy_loader=lambda: proxy, variant_factory=FakeVariant)

    with caplog.at_level(logging.WARNING):
        notifier.notify("Conectado", raw_error)

    assert "No se pudo mostrar la notificación de escritorio" in caplog.text
    assert raw_error not in caplog.text


def test_notify_swallows_proxy_loader_failure_without_exposing_exception(caplog) -> None:  # type: ignore[no-untyped-def]
    raw_error = "org.freedesktop.Notifications unavailable /secret"

    def load_proxy() -> FakeProxy:
        raise RuntimeError(raw_error)

    notifier = DesktopNotifier(proxy_loader=load_proxy, variant_factory=FakeVariant)

    with caplog.at_level(logging.WARNING):
        notifier.notify("Conectado")

    assert "No se pudo mostrar la notificación de escritorio" in caplog.text
    assert raw_error not in caplog.text
