"""Cliente de snapshot de BlueZ con proveedor de protocolo inyectable."""

from __future__ import annotations

from openbuds.infrastructure.bluez.dbus_protocol import (
    GioDBusProtocol,
    ManagedObjects,
    ManagedObjectsProvider,
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

    def __init__(self, provider: ManagedObjectsProvider | None = None) -> None:
        self._provider = provider if provider is not None else GioDBusProtocol()

    def snapshot(self) -> ManagedObjects:
        """Devuelve el snapshot obtenido por el proveedor configurado."""
        return self._provider.get_managed_objects()
