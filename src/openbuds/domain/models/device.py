"""Modelo de dispositivo Bluetooth (``org.bluez.Device1``)."""

from __future__ import annotations

from dataclasses import dataclass, field

from openbuds.domain.enums import AddressType, ConnectionState, DeviceIcon


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    """Información de un dispositivo Bluetooth remoto.

    Corresponde a ``org.bluez.Device1`` en la ruta
    ``/org/bluez/hciX/dev_XX_XX_XX_XX_XX_XX``.

    Atributos:
        object_path: Ruta D-Bus del dispositivo.
        address: Dirección MAC del dispositivo.
        name: Nombre descriptivo (puede estar vacío hasta resolver servicios).
        alias: Alias legible (editable).
        icon: Categoría derivada de ``Device1.Icon``.
        address_type: Tipo de dirección (public/random).
        paired: Si está emparejado con el adaptador local.
        connected: Si está conectado actualmente.
        trusted: Si está marcado como confianza.
        blocked: Si está bloqueado.
        services_resolved: Si los servicios GATT/SDP ya se resolvieron.
        uuids: Lista de UUIDs de servicio (vacía hasta resolver servicios).
        adapter_path: Ruta D-Bus del adaptador al que está asociado.
        connection_state: Estado de conexión derivado.
    """

    object_path: str
    address: str
    name: str
    alias: str
    icon: DeviceIcon
    address_type: AddressType
    paired: bool
    connected: bool
    trusted: bool
    blocked: bool
    services_resolved: bool
    uuids: tuple[str, ...] = field(default_factory=tuple)
    adapter_path: str = ""
    connection_state: ConnectionState = ConnectionState.UNKNOWN
