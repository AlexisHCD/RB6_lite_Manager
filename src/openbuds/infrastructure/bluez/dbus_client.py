"""Cliente de snapshot de BlueZ con proveedor de protocolo inyectable."""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Literal, cast

from openbuds.infrastructure.bluez.dbus_protocol import (
    GioDBusProtocol,
    ManagedObjects,
    ReadyCallback,
    SignalCallback,
    SignalProvider,
    SnapshotProvider,
)

# Constantes estables del servicio BlueZ D-Bus (verificadas en docs).
BLUEZ_SERVICE = "org.bluez"
BLUEZ_ROOT_PATH = "/"
BLUEZ_OBJECT_MANAGER = "org.freedesktop.DBus.ObjectManager"
DBUS_PROPERTIES = "org.freedesktop.DBus.Properties"

# Interfaces de objetos.
IFACE_ADAPTER1 = "org.bluez.Adapter1"
IFACE_DEVICE1 = "org.bluez.Device1"
IFACE_BATTERY1 = "org.bluez.Battery1"
IFACE_MEDIA_TRANSPORT1 = "org.bluez.MediaTransport1"
IFACE_MEDIA_PLAYER1 = "org.bluez.MediaPlayer1"
# NOTA: org.bluez.MediaControl1 está DEPRECATED. No usar.


class BlueZDBusClient:
    """Orquesta la obtención de snapshots sin mapearlos al dominio."""

    def __init__(self, provider: SnapshotProvider | None = None) -> None:
        self._provider = provider if provider is not None else GioDBusProtocol()

    def snapshot(self) -> ManagedObjects:
        """Devuelve el snapshot obtenido por el proveedor configurado."""
        return self._provider.get_managed_objects()

    def call_device_method(self, device_path: str, method: str) -> None:
        """Delegate an official ``Device1`` method to the provider."""
        self._provider.call_device_method(device_path, method)

    def connect_device(self, device_path: str) -> None:
        """Connect a device through ``Device1.Connect``."""
        self._provider.call_device_method(device_path, "Connect")

    def disconnect_device(self, device_path: str) -> None:
        """Disconnect a device through ``Device1.Disconnect``."""
        self._provider.call_device_method(device_path, "Disconnect")

    def subscribe(
        self,
        callback: SignalCallback,
        on_ready: ReadyCallback | None = None,
        *,
        on_poll: Callable[[], None] | None = None,
        poll_interval_ms: int | None = None,
    ) -> int:
        """Registra una callback en el proveedor configurado."""
        return cast(SignalProvider, self._provider).subscribe(
            callback,
            on_ready=on_ready,
            on_poll=on_poll,
            poll_interval_ms=poll_interval_ms,
        )

    def unsubscribe(self, subscription_id: int) -> None:
        """Cancela una suscripción en el proveedor configurado."""
        cast(SignalProvider, self._provider).unsubscribe(subscription_id)

    def close(self) -> None:
        """Cierra el proveedor configurado sin añadir semántica propia."""
        cast(SignalProvider, self._provider).close()

    def __enter__(self) -> BlueZDBusClient:
        """Devuelve el cliente para usarlo como context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        """Cierra el proveedor y deja propagarse cualquier excepción."""
        del exc_type, exc_value, traceback
        self.close()
        return False
