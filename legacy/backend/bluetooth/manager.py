"""Gestor síncrono de BlueZ sobre la API asíncrona de dbus-next."""

from __future__ import annotations

import asyncio
import inspect
import re
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from dbus_next import BusType, Variant
from dbus_next.aio import MessageBus

from ob_logging.logger import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

_BLUEZ = "org.bluez"
_OBJECT_MANAGER = "org.freedesktop.DBus.ObjectManager"
_PROPERTIES = "org.freedesktop.DBus.Properties"
_ADAPTER = "org.bluez.Adapter1"
_DEVICE = "org.bluez.Device1"
_BATTERY = "org.bluez.Battery1"
_ROOT = "/"


class BluetoothError(RuntimeError):
    """Error controlado al acceder a BlueZ o al bus system."""


@dataclass(frozen=True)
class AdapterInfo:
    """Estado observable de un adaptador Bluetooth."""

    path: str
    address: str
    name: str
    alias: str
    powered: bool
    discoverable: bool
    pairable: bool
    discovering: bool


@dataclass(frozen=True)
class DeviceInfo:
    """Estado observable de un dispositivo Bluetooth."""

    path: str
    name: str
    address: str
    rssi: int | None
    connected: bool
    paired: bool
    trusted: bool
    icon: str | None
    battery: int | None


class BluetoothManager:
    """Expone operaciones de BlueZ con una API síncrona y segura."""

    def __init__(self, bus_factory: Callable[[], Any] | None = None) -> None:
        self._bus_factory = bus_factory or (lambda: MessageBus(bus_type=BusType.SYSTEM))
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, name="openbuds-dbus", daemon=True)
        self._bus: Any = None
        self._closed = False
        self._thread.start()
        try:
            self._run(self._connect())
        except Exception as exc:
            self.close()
            raise BluetoothError(f"BlueZ/DBus no está disponible: {exc}") from exc

    def _run_loop(self) -> None:
        """Ejecuta el event loop privado de la instancia."""
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _connect(self) -> None:
        bus = self._bus_factory()
        if inspect.isawaitable(bus):
            bus = await bus
        self._bus = bus
        await bus.connect()
        await self._get_managed_objects()

    def _run(self, coroutine: Coroutine[Any, Any, Any]) -> Any:
        """Ejecuta una corrutina en el event loop privado."""
        if self._closed:
            raise BluetoothError("BluetoothManager está cerrado")
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        try:
            return future.result()
        except BluetoothError:
            raise
        except Exception as exc:
            raise BluetoothError(f"Error comunicando con BlueZ: {exc}") from exc

    def close(self) -> None:
        """Cierra la conexión DBus y el event loop privado."""
        if self._closed:
            return
        self._closed = True
        if self._bus is not None and self._thread.is_alive():
            future = asyncio.run_coroutine_threadsafe(self._disconnect(), self._loop)
            try:
                future.result(timeout=2)
            except Exception as exc:
                logger.debug("No se pudo cerrar DBus limpiamente: %s", exc)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2)
        self._loop.close()

    def __enter__(self) -> BluetoothManager:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    async def _disconnect(self) -> None:
        if self._bus is not None:
            self._bus.disconnect()

    async def _get_managed_objects(self) -> dict[str, dict[str, dict[str, Any]]]:
        if self._bus is None:
            raise BluetoothError("No hay conexión con el bus system")
        proxy = self._bus.get_proxy_object(_BLUEZ, _ROOT, await self._introspect(_ROOT))
        manager = proxy.get_interface(_OBJECT_MANAGER)
        objects = await manager.call_get_managed_objects()
        return cast("dict[str, dict[str, dict[str, Any]]]", objects)

    async def _introspect(self, path: str) -> Any:
        return await self._bus.introspect(_BLUEZ, path)

    async def _proxy(self, path: str) -> Any:
        return self._bus.get_proxy_object(_BLUEZ, path, await self._introspect(path))

    @staticmethod
    def _value(properties: dict[str, Any], name: str, default: Any = None) -> Any:
        value = properties.get(name, default)
        return getattr(value, "value", value)

    def adapters(self) -> tuple[AdapterInfo, ...]:
        """Devuelve todos los adaptadores expuestos por BlueZ."""
        return cast("tuple[AdapterInfo, ...]", self._run(self._adapters()))

    def list_adapters(self) -> tuple[AdapterInfo, ...]:
        """Alias explícito para listar adaptadores."""
        return self.adapters()

    async def _adapters(self) -> tuple[AdapterInfo, ...]:
        objects = await self._get_managed_objects()
        result = []
        for path, interfaces in objects.items():
            properties = interfaces.get(_ADAPTER)
            if properties is None:
                continue
            result.append(AdapterInfo(path, self._value(properties, "Address", ""),
                                      self._value(properties, "Name", ""),
                                      self._value(properties, "Alias", ""),
                                      self._value(properties, "Powered", False),
                                      self._value(properties, "Discoverable", False),
                                      self._value(properties, "Pairable", False),
                                      self._value(properties, "Discovering", False)))
        return tuple(result)

    def devices(self) -> tuple[DeviceInfo, ...]:
        """Devuelve todos los dispositivos conocidos por BlueZ."""
        return cast("tuple[DeviceInfo, ...]", self._run(self._devices()))

    def list_devices(self) -> tuple[DeviceInfo, ...]:
        """Alias explícito para listar dispositivos."""
        return self.devices()

    async def _devices(self) -> tuple[DeviceInfo, ...]:
        objects = await self._get_managed_objects()
        result = []
        for path, interfaces in objects.items():
            properties = interfaces.get(_DEVICE)
            if properties is None:
                continue
            battery_properties = interfaces.get(_BATTERY, {})
            result.append(DeviceInfo(path, self._value(properties, "Name", ""),
                                     self._value(properties, "Address", ""),
                                     self._value(properties, "RSSI"),
                                     self._value(properties, "Connected", False),
                                     self._value(properties, "Paired", False),
                                     self._value(properties, "Trusted", False),
                                     self._value(properties, "Icon"),
                                     self._value(battery_properties, "Percentage")))
        return tuple(result)

    def _adapter_method(self, adapter_path: str, method: str) -> None:
        self._run(self._call_interface(adapter_path, _ADAPTER, method))

    async def _call_interface(self, path: str, interface_name: str, method: str) -> None:
        proxy = await self._proxy(path)
        method_name = re.sub(r"(?<!^)([A-Z])", r"_\1", method).lower()
        await getattr(proxy.get_interface(interface_name), f"call_{method_name}")()

    def start_discovery(self, adapter_path: str) -> None:
        """Inicia el descubrimiento en un adaptador."""
        self._adapter_method(adapter_path, "StartDiscovery")

    def stop_discovery(self, adapter_path: str) -> None:
        """Detiene el descubrimiento en un adaptador."""
        self._adapter_method(adapter_path, "StopDiscovery")

    def discover(self, adapter_path: str, timeout: float = 10.0) -> None:
        """Descubre dispositivos durante `timeout` segundos y detiene el scan."""
        self._run(self._discover(adapter_path, timeout))

    async def _discover(self, adapter_path: str, timeout: float) -> None:
        await self._call_interface(adapter_path, _ADAPTER, "StartDiscovery")
        try:
            await asyncio.sleep(timeout)
        finally:
            await self._call_interface(adapter_path, _ADAPTER, "StopDiscovery")

    def _set_adapter(self, path: str, property_name: str, signature: str, value: Any) -> None:
        self._run(self._set_property(path, _ADAPTER, property_name, signature, value))

    async def _set_property(self, path: str, interface_name: str, name: str,
                            signature: str, value: Any) -> None:
        proxy = await self._proxy(path)
        properties = proxy.get_interface(_PROPERTIES)
        await properties.call_set(interface_name, name, Variant(signature, value))

    def set_powered(self, path: str, value: bool) -> None:
        self._set_adapter(path, "Powered", "b", value)

    def set_discoverable(self, path: str, value: bool) -> None:
        self._set_adapter(path, "Discoverable", "b", value)

    def set_pairable(self, path: str, value: bool) -> None:
        self._set_adapter(path, "Pairable", "b", value)

    def set_alias(self, path: str, value: str) -> None:
        self._set_adapter(path, "Alias", "s", value)

    def _device_method(self, path: str, method: str) -> None:
        self._run(self._call_interface(path, _DEVICE, method))

    def connect(self, path: str) -> None:
        """Conecta un dispositivo."""
        self._device_method(path, "Connect")

    def disconnect(self, path: str) -> None:
        """Desconecta un dispositivo."""
        self._device_method(path, "Disconnect")

    def pair(self, path: str) -> None:
        """Empareja un dispositivo."""
        self._device_method(path, "Pair")

    def set_trusted(self, path: str, value: bool) -> None:
        """Marca o desmarca un dispositivo como confiable."""
        self._run(self._set_property(path, _DEVICE, "Trusted", "b", value))

    def remove_device(self, adapter_path: str, device_path: str) -> None:
        """Elimina un dispositivo de la base de datos del adaptador."""
        self._run(self._remove_device(adapter_path, device_path))

    async def _remove_device(self, adapter_path: str, device_path: str) -> None:
        proxy = await self._proxy(adapter_path)
        manager = proxy.get_interface(_ADAPTER)
        await manager.call_remove_device(device_path)
