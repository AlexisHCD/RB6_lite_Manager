"""Caso de uso: obtener información agregada de un dispositivo.

Combina datos de BlueZ (dispositivo, batería, RSSI) y de PipeWire/WirePlumber
(códec activo) en una vista unificada para la UI.

Estado: Fase 1 — contrato definido, sin implementación (Fase 3/4).
"""

from __future__ import annotations

from dataclasses import dataclass

from openbuds.domain.interfaces import IAudioRepository, IBluetoothRepository
from openbuds.domain.models import BatteryLevel, CodecInfo, DeviceInfo, RSSIReading


@dataclass(frozen=True, slots=True)
class DeviceAggregate:
    """Vista agregada de toda la información disponible de un dispositivo.

    Cada componente es opcional (``None``) si no está disponible, porque la
    disponibilidad depende del estado del dispositivo (conectado, servicios
    resueltos, perfiles activos).
    """

    device: DeviceInfo
    battery: BatteryLevel | None
    rssi: RSSIReading | None
    codec: CodecInfo | None


class GetDeviceInfoUseCase:
    """Recopila toda la información disponible de un dispositivo."""

    def __init__(
        self,
        bluetooth_repo: IBluetoothRepository,
        audio_repo: IAudioRepository,
    ) -> None:
        self._bluetooth = bluetooth_repo
        self._audio = audio_repo

    def execute(self, device_path: str) -> DeviceAggregate | None:
        """Devuelve la información agregada del dispositivo, o ``None``."""
        raise NotImplementedError("Implementación diferida a Fase 3/4.")
