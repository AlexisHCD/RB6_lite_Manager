"""Best-effort desktop notifications through the session D-Bus."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Protocol, cast

from openbuds.presentation.formatting import sanitize_display_field

_LOGGER = logging.getLogger(__name__)
_SERVICE = "org.freedesktop.Notifications"
_OBJECT_PATH = "/org/freedesktop/Notifications"
_INTERFACE = "org.freedesktop.Notifications"
_APP_NAME = "OpenBuds Manager"
_NOTIFY_SIGNATURE = "(susssasa{sv}i)"
_EXPIRE_TIMEOUT = -1  # Let the notification server choose its normal lifetime.
_NOTIFICATION_WARNING = "No se pudo mostrar la notificación de escritorio."


class _NotificationProxy(Protocol):
    """Small part of ``Gio.DBusProxy`` used by the adapter."""

    def call_sync(
        self,
        method_name: str,
        parameters: object,
        flags: int,
        timeout_msec: int,
        cancellable: object | None,
    ) -> object:
        """Call a D-Bus method synchronously."""


ProxyLoader = Callable[[], _NotificationProxy]
VariantFactory = Callable[[str, object], object]


def _load_session_proxy() -> _NotificationProxy:
    """Create the freedesktop notifications proxy only when first needed."""
    import gi

    gi.require_version("Gio", "2.0")
    from gi.repository import Gio

    return cast(
        _NotificationProxy,
        Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SESSION,
            Gio.DBusProxyFlags.NONE,
            None,
            _SERVICE,
            _OBJECT_PATH,
            _INTERFACE,
            None,
        ),
    )


def _make_variant(signature: str, value: object) -> Any:
    """Build a GLib variant lazily so module import has no D-Bus requirement."""
    import gi

    gi.require_version("GLib", "2.0")
    from gi.repository import GLib

    return GLib.Variant(signature, value)


def _sanitize_notification_field(value: str) -> str:
    """Apply the shared privacy protections to a notification field."""
    return sanitize_display_field(value)


class DesktopNotifier:
    """Best-effort adapter for ``org.freedesktop.Notifications``."""

    def __init__(
        self,
        *,
        proxy_loader: ProxyLoader | None = None,
        variant_factory: VariantFactory | None = None,
    ) -> None:
        """Prepare the adapter without opening a session-bus connection."""
        self._proxy_loader = proxy_loader or _load_session_proxy
        self._variant_factory = variant_factory or _make_variant
        self._proxy: _NotificationProxy | None = None

    def notify(self, summary: str, body: str = "") -> None:
        """Send one notification, ignoring unavailable desktop services.

        The ``-1`` expiration asks the notification server to use its normal
        lifetime rather than imposing an application-specific timeout.
        """
        safe_summary = _sanitize_notification_field(summary)
        safe_body = _sanitize_notification_field(body)
        try:
            parameters = self._variant_factory(
                _NOTIFY_SIGNATURE,
                (_APP_NAME, 0, "", safe_summary, safe_body, [], {}, _EXPIRE_TIMEOUT),
            )
            if self._proxy is None:
                self._proxy = self._proxy_loader()
            self._proxy.call_sync("Notify", parameters, 0, -1, None)
        except Exception:
            self._proxy = None
            _LOGGER.warning(_NOTIFICATION_WARNING)
