"""Mapeo puro de propiedades D-Bus de BlueZ a modelos del dominio."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from openbuds.core.errors import BluetoothError
from openbuds.domain.enums import AddressType, ConnectionState, DeviceIcon
from openbuds.domain.models import AdapterInfo, BatteryLevel, DeviceInfo, RSSIReading


def _type_error(interface: str, property_name: str, expected: str, value: object) -> BluetoothError:
    return BluetoothError(
        f"{interface}.{property_name}: se esperaba {expected}, recibido {type(value).__name__}"
    )


def _required_str(props: Mapping[str, object], interface: str, property_name: str) -> str:
    if property_name not in props:
        raise BluetoothError(f"{interface}.{property_name}: propiedad requerida ausente")
    value = props[property_name]
    if not isinstance(value, str):
        raise _type_error(interface, property_name, "str", value)
    return value


def _optional_str(
    props: Mapping[str, object], interface: str, property_name: str, default: str
) -> str:
    if property_name not in props:
        return default
    value = props[property_name]
    if not isinstance(value, str):
        raise _type_error(interface, property_name, "str", value)
    return value


def _optional_bool(
    props: Mapping[str, object], interface: str, property_name: str, default: bool
) -> bool:
    if property_name not in props:
        return default
    value = props[property_name]
    if type(value) is not bool:
        raise _type_error(interface, property_name, "bool", value)
    return value


def _optional_enum[EnumType: StrEnum](
    props: Mapping[str, object], interface: str, property_name: str, enum: type[EnumType]
) -> EnumType:
    if property_name not in props:
        return enum("unknown")
    value = props[property_name]
    if not isinstance(value, str):
        raise _type_error(interface, property_name, "str", value)
    try:
        return enum(value)
    except ValueError:
        return enum("unknown")


def _optional_int(props: Mapping[str, object], interface: str, property_name: str) -> int | None:
    if property_name not in props:
        return None
    value = props[property_name]
    if not isinstance(value, int) or isinstance(value, bool):
        raise _type_error(interface, property_name, "int", value)
    return value


def _optional_uuids(props: Mapping[str, object], interface: str) -> tuple[str, ...]:
    if "UUIDs" not in props:
        return ()
    value = props["UUIDs"]
    if not isinstance(value, (list, tuple)):
        raise _type_error(interface, "UUIDs", "list or tuple[str, ...]", value)
    if any(not isinstance(uuid, str) for uuid in value):
        raise BluetoothError(f"{interface}.UUIDs: todos los elementos deben ser str")
    return tuple(value)


def map_adapter(object_path: str, props: Mapping[str, object]) -> AdapterInfo:
    """Construye un ``AdapterInfo`` desde propiedades completas de ``Adapter1``."""
    return AdapterInfo(
        object_path=object_path,
        address=_required_str(props, "Adapter1", "Address"),
        name=_optional_str(props, "Adapter1", "Name", ""),
        alias=_optional_str(props, "Adapter1", "Alias", ""),
        powered=_optional_bool(props, "Adapter1", "Powered", False),
        discoverable=_optional_bool(props, "Adapter1", "Discoverable", False),
        pairable=_optional_bool(props, "Adapter1", "Pairable", False),
        discovering=_optional_bool(props, "Adapter1", "Discovering", False),
        address_type=_optional_enum(props, "Adapter1", "AddressType", AddressType),
    )


def map_device(object_path: str, props: Mapping[str, object]) -> DeviceInfo:
    """Construye un ``DeviceInfo`` desde propiedades completas de ``Device1``."""
    connected = _optional_bool(props, "Device1", "Connected", False)
    return DeviceInfo(
        object_path=object_path,
        address=_required_str(props, "Device1", "Address"),
        adapter_path=_required_str(props, "Device1", "Adapter"),
        name=_optional_str(props, "Device1", "Name", ""),
        alias=_optional_str(props, "Device1", "Alias", ""),
        icon=_optional_enum(props, "Device1", "Icon", DeviceIcon),
        address_type=_optional_enum(props, "Device1", "AddressType", AddressType),
        paired=_optional_bool(props, "Device1", "Paired", False),
        connected=connected,
        connection_state=(ConnectionState.CONNECTED if connected else ConnectionState.DISCONNECTED),
        trusted=_optional_bool(props, "Device1", "Trusted", False),
        blocked=_optional_bool(props, "Device1", "Blocked", False),
        services_resolved=_optional_bool(props, "Device1", "ServicesResolved", False),
        uuids=_optional_uuids(props, "Device1"),
    )


def map_battery(props: Mapping[str, object]) -> BatteryLevel:
    """Construye un ``BatteryLevel`` desde propiedades completas de ``Battery1``."""
    percentage = _optional_int(props, "Battery1", "Percentage")
    try:
        return BatteryLevel(
            percentage=percentage,
            source=_optional_str(props, "Battery1", "Source", ""),
        )
    except ValueError as exc:
        raise BluetoothError(f"Battery1.Percentage fuera de rango [0, 100]: {percentage}") from exc


def map_rssi(props: Mapping[str, object], *, timestamp: datetime | None = None) -> RSSIReading:
    """Construye una lectura desde propiedades completas de ``Device1``."""
    if timestamp is None:
        reading_timestamp = datetime.now(UTC)
    elif (
        not isinstance(timestamp, datetime)
        or timestamp.tzinfo is None
        or timestamp.utcoffset() != timedelta(0)
    ):
        raise BluetoothError("Device1.timestamp: se esperaba datetime UTC aware")
    else:
        reading_timestamp = timestamp

    rssi = _optional_int(props, "Device1", "RSSI")
    tx_power = _optional_int(props, "Device1", "TxPower")
    try:
        return RSSIReading(
            rssi_dbm=rssi,
            timestamp=reading_timestamp,
            tx_power_dbm=tx_power,
        )
    except ValueError as exc:
        raise BluetoothError(f"Device1.RSSI fuera de rango: {rssi}") from exc
