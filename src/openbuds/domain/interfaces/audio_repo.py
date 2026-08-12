"""Contrato del repositorio de audio (PipeWire / WirePlumber).

Implementación de referencia: ``openbuds.infrastructure.pipewire.pipewire_repository``
y ``openbuds.infrastructure.wireplumber.wpctl_adapter``.
"""

from __future__ import annotations

from openbuds.domain.models import BluetoothAudioNode, CodecInfo


class IAudioRepository:
    """Acceso al estado del grafo de audio PipeWire/WirePlumber.

    Debido a la inexistencia de un binding Python oficial de PipeWire
    (ver ADR-0003), la implementación se basa en parsear ``pw-dump`` (JSON) y
    usar ``wpctl inspect <id>`` vía ``subprocess``.

    Esta interfaz es de solo lectura sobre el estado de audio.
    """

    def get_active_codec(self, device_address: str) -> CodecInfo | None:
        """Devuelve el códec activo para el dispositivo Bluetooth dado.

        Combina la información del nodo PipeWire (``device.profile`` /
        ``bluez5.codec``) con el byte ``MediaTransport1.Codec`` de BlueZ.

        Nota: los nombres de propiedades runtime ``bluez5.codec`` y
        ``api.bluez5.transport`` no están documentados formalmente; se validan
        empíricamente (ver docs/RESEARCH_LIMITS.md).
        """
        raise NotImplementedError

    def list_bluetooth_audio_nodes(self) -> list[BluetoothAudioNode]:
        """Devuelve los nodos de audio Bluetooth (sinks/sources) registrados.

        Las propiedades runtime se conservan como valores observados en el
        modelo tipado, sin inferir capacidades.
        """
        raise NotImplementedError

    def list_device_audio_nodes(self, device_address: str) -> list[BluetoothAudioNode]:
        """Devuelve los nodos Bluetooth asociados a una dirección de dispositivo."""
        raise NotImplementedError

    def get_default_audio_sink(self) -> str | None:
        """Devuelve el nombre del sink de audio por defecto, si existe."""
        raise NotImplementedError
