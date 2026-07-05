"""Adaptador de BlueZ vía D-Bus usando PyGObject/Gio (GDBus).

Estado: Fase 1 — esqueleto. La implementación completa (suscripción a señales,
mapeo de object paths, lectura de propiedades) se desarrolla en Fase 3.

Referencias verificadas:
  - Servicio D-Bus: ``org.bluez``
  - ObjectManager en la raíz ``/``: GetManagedObjects, InterfacesAdded/Removed.
  - Interfaces: Adapter1, Device1, Battery1, MediaTransport1, MediaPlayer1.
  - MediaControl1 está DEPRECATED: no usar.

Ver ADR-0001 y docs/bluez/dbus-interfaces.md.
"""

from __future__ import annotations

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
    """Cliente D-Bus para BlueZ sobre el bus del sistema.

    Estado: Fase 1 — sin implementación.
    Encapsula la conexión GDBus, el snapshot inicial (GetManagedObjects) y las
    suscripciones a PropertiesChanged/InterfacesAdded/InterfacesRemoved.
    """

    def __init__(self) -> None:
        raise NotImplementedError("Implementación diferada a Fase 3 (Bluetooth).")
