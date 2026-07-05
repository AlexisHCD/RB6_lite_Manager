"""Contrato del repositorio Bluetooth (acceso a BlueZ vía D-Bus).

Implementación de referencia: ``openbuds.infrastructure.bluez.bluez_repository``.
"""

from __future__ import annotations

from openbuds.domain.interfaces.observer import DeviceChangeCallback
from openbuds.domain.models import AdapterInfo, BatteryLevel, DeviceInfo, RSSIReading


class IBluetoothRepository:
    """Acceso de solo lectura al estado Bluetooth del sistema vía BlueZ.

    Responsabilidades:
      - Listar adaptadores y dispositivos conocidos.
      - Obtener datos derivados (batería, RSSI) de un dispositivo.
      - Suscribirse a cambios de estado (conexión/desconexión, propiedades).

    IMPORTANTE: esta interfaz es de SOLO LECTURA sobre el estado del dispositivo.
    No envía comandos al hardware. El proyecto no escribe en el dispositivo
    Bluetooth (ver filosofía del proyecto y docs/RESTRICTIONES).
    """

    def list_adapters(self) -> list[AdapterInfo]:
        """Devuelve todos los adaptadores Bluetooth locales detectados."""
        raise NotImplementedError

    def list_devices(self, adapter_path: str | None = None) -> list[DeviceInfo]:
        """Devuelve los dispositivos conocidos.

        Args:
            adapter_path: Si se indica, filtra por el adaptador dado. Si es
                ``None``, devuelve los dispositivos de todos los adaptadores.

        """
        raise NotImplementedError

    def get_device(self, device_path: str) -> DeviceInfo | None:
        """Devuelve la información de un dispositivo por su ruta D-Bus."""
        raise NotImplementedError

    def get_battery(self, device_path: str) -> BatteryLevel | None:
        """Devuelve el nivel de batería del dispositivo, si expone ``Battery1``."""
        raise NotImplementedError

    def get_rssi(self, device_path: str) -> RSSIReading | None:
        """Devuelve una lectura puntual de RSSI/TxPower del dispositivo."""
        raise NotImplementedError

    def subscribe_device_changes(self, callback: DeviceChangeCallback) -> None:
        """Registra un callback para notificar cambios en dispositivos.

        La implementación se basa en las señales D-Bus estándar de BlueZ:
        ``InterfacesAdded``, ``InterfacesRemoved`` y ``PropertiesChanged``.
        """
        raise NotImplementedError
