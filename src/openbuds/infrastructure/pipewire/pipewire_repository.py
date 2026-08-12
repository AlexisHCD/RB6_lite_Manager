"""Implementación de ``IAudioRepository`` sobre PipeWire.

Incremento 1: ejecución de ``pw-dump`` y listado de nodos Bluetooth.

Justificación (ADR-0003): no existe binding Python oficial de PipeWire. La
inspección fiable se hace parseando ``pw-dump`` (JSON) y ``wpctl inspect``.
"""

from __future__ import annotations

from typing import Protocol

from openbuds.domain.enums import BluetoothProfile, CodecType
from openbuds.domain.interfaces import IAudioRepository
from openbuds.domain.models import BluetoothAudioNode, CodecInfo
from openbuds.infrastructure.pipewire.node_mapper import match_nodes_by_address, to_domain_node
from openbuds.infrastructure.pipewire.pw_dump_parser import parse_bluetooth_audio_nodes
from openbuds.infrastructure.pipewire.pw_dump_runner import PwDumpRunner


class DumpRunner(Protocol):
    """Contrato mínimo para obtener la salida textual de ``pw-dump``."""

    def dump(self) -> str:
        """Return the output produced by ``pw-dump``."""
        ...


class PipeWireRepository(IAudioRepository):
    """Repositorio de audio basado en las CLI de PipeWire/WirePlumber.

    Incremento 1: listado de nodos Bluetooth desde ``pw-dump``.
    """

    def __init__(self, runner: DumpRunner | None = None) -> None:
        """Create the repository with an injectable ``pw-dump`` runner."""
        self._runner = runner if runner is not None else PwDumpRunner()

    def get_active_codec(self, device_address: str) -> CodecInfo | None:
        flat_nodes = parse_bluetooth_audio_nodes(self._runner.dump())
        nodes = match_nodes_by_address(device_address, flat_nodes)
        for node in nodes:
            if not node.profile or not node.codec:
                continue
            if node.profile == "off":
                return None
            profile = {
                "a2dp-sink": BluetoothProfile.A2DP,
                "a2dp-source": BluetoothProfile.A2DP,
                "headset-head-unit": BluetoothProfile.HFP,
            }.get(node.profile or "", BluetoothProfile.UNKNOWN)
            try:
                codec = CodecType(node.codec)
            except ValueError:
                codec = CodecType.UNKNOWN
            return CodecInfo(
                codec=codec,
                profile=profile,
                a2dp_codec_byte=None,
                verified=profile in (BluetoothProfile.A2DP, BluetoothProfile.HFP)
                and codec is not CodecType.UNKNOWN,
                configuration_hex="",
            )
        return None

    def list_bluetooth_audio_nodes(self) -> list[BluetoothAudioNode]:
        return [to_domain_node(node) for node in parse_bluetooth_audio_nodes(self._runner.dump())]

    def list_device_audio_nodes(self, device_address: str) -> list[BluetoothAudioNode]:
        """List typed nodes associated with one Bluetooth address."""
        flat_nodes = parse_bluetooth_audio_nodes(self._runner.dump())
        return match_nodes_by_address(device_address, flat_nodes)

    def get_default_audio_sink(self) -> str | None:
        raise NotImplementedError(
            "Implementación pendiente de la Etapa 2, sujeta a evidencia de la Etapa 1."
        )
