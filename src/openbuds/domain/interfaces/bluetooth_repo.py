"""Contrato del repositorio Bluetooth (acceso a BlueZ vía D-Bus).

Implementación de referencia: ``openbuds.infrastructure.bluez.bluez_repository``.
"""

from __future__ import annotations

from openbuds.domain.interfaces.observer import DeviceChangeCallback, Unsubscribe
from openbuds.domain.models import AdapterInfo, BatteryLevel, DeviceInfo, RSSIReading


class IBluetoothRepository:
    """Access Bluetooth state and explicit session operations.

    Responsabilidades:
      - Listar adaptadores y dispositivos conocidos.
      - Obtener datos derivados (batería, RSSI) de un dispositivo.
      - Suscribirse a cambios de estado (conexión/desconexión, propiedades).

    Queries are read-only. ``connect`` and ``disconnect`` use the official
    ``org.bluez.Device1`` methods and mutate only connection state, not pairing.
    User approval is required before execution against a real system.
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

    def subscribe_device_changes(self, callback: DeviceChangeCallback) -> Unsubscribe:
        """Registra un callback para notificar cambios en dispositivos.

        La implementación se basa en las señales D-Bus estándar de BlueZ:
        ``InterfacesAdded``, ``InterfacesRemoved`` y ``PropertiesChanged``.
        """
        raise NotImplementedError

    def connect(self, device_path: str) -> None:
        """Conecta el dispositivo mediante ``org.bluez.Device1.Connect``."""
        raise NotImplementedError

    def disconnect(self, device_path: str) -> None:
        """Desconecta el dispositivo mediante ``org.bluez.Device1.Disconnect``."""
        raise NotImplementedError
