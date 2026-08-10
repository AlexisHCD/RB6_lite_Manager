"""Modelo de adaptador Bluetooth (``org.bluez.Adapter1``)."""

from __future__ import annotations

from dataclasses import dataclass

from openbuds.domain.enums import AddressType


@dataclass(frozen=True, slots=True)
class AdapterInfo:
    """Información de un adaptador Bluetooth local (HCI controller).

    Corresponde a ``org.bluez.Adapter1`` en la ruta ``/org/bluez/hciX``.

    Atributos:
        object_path: Ruta D-Bus del adaptador, p. ej. ``/org/bluez/hci0``.
        address: Dirección MAC del adaptador (formato ``XX:XX:XX:XX:XX:XX``).
        name: Nombre del adaptador.
        alias: Alias legible (editable).
        powered: Si el adaptador está encendido.
        discoverable: Si es detectable por otros dispositivos.
        pairable: Si acepta emparejamientos.
        discovering: Si está realizando un escaneo activo.
        address_type: Tipo de dirección (public/random).
    """

    object_path: str
    address: str
    name: str
    alias: str
    powered: bool
    discoverable: bool
    pairable: bool
    discovering: bool
    address_type: AddressType = AddressType.UNKNOWN
