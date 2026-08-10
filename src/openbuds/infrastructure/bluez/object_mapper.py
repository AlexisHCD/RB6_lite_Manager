"""Mapeo de estructuras D-Bus de BlueZ a modelos del dominio.

Convierte diccionarios de propiedades D-Bus (variantes GLib) en dataclasses
inmutables del dominio. Aísla toda la lógica de parseo de variantes aquí para
que el resto del código trabaje con tipos puros de Python.

Estado: Fase 1 — esqueleto. Implementación completa en Fase 3.
"""

from __future__ import annotations

from openbuds.domain.enums import AddressType, DeviceIcon
from openbuds.domain.models import AdapterInfo, BatteryLevel, DeviceInfo


def _coerce_address_type(raw: str | None) -> AddressType:
    """Convierte el string crudo de AddressType al enum, con fallback segura."""
    if raw is None:
        return AddressType.UNKNOWN
    try:
        return AddressType(raw)
    except ValueError:
        return AddressType.UNKNOWN


def _coerce_icon(raw: str | None) -> DeviceIcon:
    """Convierte el string crudo de Icon al enum, con fallback segura."""
    if raw is None:
        return DeviceIcon.UNKNOWN
    try:
        return DeviceIcon(raw)
    except ValueError:
        return DeviceIcon.UNKNOWN


def map_adapter(object_path: str, props: dict) -> AdapterInfo:
    """Construye un ``AdapterInfo`` desde las propiedades D-Bus de Adapter1.

    Estado: Fase 1 — firma definida; implementación completa en Fase 3.
    """
    raise NotImplementedError("Implementación diferada a Fase 3 (Bluetooth).")


def map_device(object_path: str, props: dict) -> DeviceInfo:
    """Construye un ``DeviceInfo`` desde las propiedades D-Bus de Device1.

    Estado: Fase 1 — firma definida; implementación completa en Fase 3.
    """
    raise NotImplementedError("Implementación diferada a Fase 3 (Bluetooth).")


def map_battery(props: dict) -> BatteryLevel:
    """Construye un ``BatteryLevel`` desde las propiedades D-Bus de Battery1.

    Estado: Fase 1 — firma definida; implementación completa en Fase 3.
    """
    raise NotImplementedError("Implementación diferada a Fase 3 (Bluetooth).")
