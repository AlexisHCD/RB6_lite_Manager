"""Caso de uso: escanear y listar dispositivos Bluetooth.

Estado: Fase 1 — contrato definido, sin implementación (Fase 3).
"""

from __future__ import annotations

from dataclasses import dataclass

from openbuds.domain.interfaces import IBluetoothRepository
from openbuds.domain.models import DeviceInfo


@dataclass(frozen=True, slots=True)
class ScanDevicesRequest:
    """Parámetros del escaneo.

    Atributos:
        adapter_path: Adaptador a usar, o ``None`` para el por defecto.
        include_paired_only: Si solo se devuelven dispositivos emparejados.
    """

    adapter_path: str | None = None
    include_paired_only: bool = False


class ScanDevicesUseCase:
    """Lista los dispositivos Bluetooth conocidos por el sistema.

    Depende solo de ``IBluetoothRepository`` (DIP). La implementación concreta
    de acceso a BlueZ se inyecta.
    """

    def __init__(self, bluetooth_repo: IBluetoothRepository) -> None:
        self._bluetooth = bluetooth_repo

    def execute(self, request: ScanDevicesRequest) -> list[DeviceInfo]:
        """Devuelve los dispositivos detectados según el request."""
        devices = self._bluetooth.list_devices(request.adapter_path)
        if request.include_paired_only:
            return [d for d in devices if d.paired]
        return devices
