"""Use case for collecting aggregated device information.

Combines BlueZ device, battery, and RSSI data with the active PipeWire codec
in one view for the UI.

Stage 2: implemented and validated with Stage 1 hardware evidence (A2DP/SBC).
"""

from __future__ import annotations

from dataclasses import dataclass

from openbuds.domain.interfaces import IAudioRepository, IBluetoothRepository
from openbuds.domain.models import (
    BatteryLevel,
    BluetoothAudioNode,
    CodecInfo,
    DeviceInfo,
    RSSIReading,
)


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
    audio_nodes: tuple[BluetoothAudioNode, ...] = ()


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
        """Return the aggregated device information, or ``None``."""
        device = self._bluetooth.get_device(device_path)
        if device is None:
            return None
        return DeviceAggregate(
            device=device,
            battery=self._bluetooth.get_battery(device_path),
            rssi=self._bluetooth.get_rssi(device_path),
            codec=self._audio.get_active_codec(device.address),
            audio_nodes=tuple(self._audio.list_device_audio_nodes(device.address)),
        )
