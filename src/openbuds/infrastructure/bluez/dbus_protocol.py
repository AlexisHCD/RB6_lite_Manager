"""Protocolo de snapshot de BlueZ mediante el proxy síncrono de Gio."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, cast

from openbuds.core.errors import BluetoothError

type ManagedObjects = dict[str, dict[str, dict[str, object]]]
type GILoader = Callable[[], tuple[Any, Any]]
DBUS_CALL_TIMEOUT_MS = 5000
_EXPECTED_SIGNATURE = "(a{oa{sa{sv}}})"


class ManagedObjectsProvider(Protocol):
    """Fuente interna capaz de obtener un snapshot nativo de BlueZ."""

    def get_managed_objects(self) -> ManagedObjects:
        """Devuelve el árbol de objetos administrados por BlueZ."""
        ...


def _load_gi() -> tuple[Any, Any]:
    """Carga Gio y GLib solo cuando se construye el adaptador real."""
    import gi

    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib

    return Gio, GLib


def _validate_snapshot(value: object) -> ManagedObjects:
    """Comprueba la forma completa del resultado desempaquetado."""
    if not isinstance(value, dict):
        raise BluetoothError("El snapshot de BlueZ no tiene forma de diccionario")

    for object_path, interfaces in value.items():
        if not isinstance(object_path, str):
            raise BluetoothError("El snapshot de BlueZ contiene una ruta de objeto inválida")
        if not isinstance(interfaces, dict):
            raise BluetoothError("El snapshot de BlueZ contiene interfaces inválidas")
        for interface_name, properties in interfaces.items():
            if not isinstance(interface_name, str) or not isinstance(properties, dict):
                raise BluetoothError("El snapshot de BlueZ contiene propiedades inválidas")
            if any(not isinstance(property_name, str) for property_name in properties):
                raise BluetoothError("El snapshot de BlueZ contiene nombres de propiedad inválidos")

    return cast(ManagedObjects, value)


class GioDBusProtocol:
    """Proveedor de snapshots de BlueZ usando ``GetManagedObjects``."""

    def __init__(self, loader: GILoader | None = None) -> None:
        try:
            gio, glib = (loader or _load_gi)()
        except (ImportError, ValueError) as exc:
            raise BluetoothError(
                "No se pudo cargar PyGObject/Gio; instala el runtime y ejecuta make check-runtime"
            ) from exc

        self._gio = gio
        self._glib = glib
        try:
            self._proxy = self._gio.DBusProxy.new_for_bus_sync(
                self._gio.BusType.SYSTEM,
                self._gio.DBusProxyFlags.DO_NOT_AUTO_START,
                None,
                "org.bluez",
                "/",
                "org.freedesktop.DBus.ObjectManager",
                None,
            )
        except self._glib.Error as exc:
            raise BluetoothError(f"No se pudo construir el proxy de BlueZ: {exc}") from exc

    def get_managed_objects(self) -> ManagedObjects:
        """Obtiene y valida un snapshot de objetos administrados por BlueZ."""
        try:
            reply = self._proxy.call_sync(
                "GetManagedObjects",
                None,
                self._gio.DBusCallFlags.NO_AUTO_START,
                DBUS_CALL_TIMEOUT_MS,
                None,
            )
        except self._glib.Error as exc:
            raise BluetoothError(f"No se pudo obtener el snapshot de BlueZ: {exc}") from exc

        if reply.get_type_string() != _EXPECTED_SIGNATURE:
            raise BluetoothError("La respuesta de BlueZ tiene una firma GVariant inesperada")

        unpacked = reply.unpack()
        if not isinstance(unpacked, tuple) or len(unpacked) != 1:
            raise BluetoothError("La respuesta de BlueZ tiene una forma desempaquetada inválida")

        return _validate_snapshot(unpacked[0])
