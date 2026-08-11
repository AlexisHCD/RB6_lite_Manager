"""Implementación de ``IAudioRepository`` sobre PipeWire.

Incremento 1: ejecución de ``pw-dump`` y listado de nodos Bluetooth.

Justificación (ADR-0003): no existe binding Python oficial de PipeWire. La
inspección fiable se hace parseando ``pw-dump`` (JSON) y ``wpctl inspect``.
"""

from __future__ import annotations

from typing import Protocol

from openbuds.domain.interfaces import IAudioRepository
from openbuds.domain.models import CodecInfo
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
        raise NotImplementedError("Implementación pendiente en la siguiente Fase 4 (Audio).")

    def list_bluetooth_audio_nodes(self) -> list[dict[str, str]]:
        return parse_bluetooth_audio_nodes(self._runner.dump())

    def get_default_audio_sink(self) -> str | None:
        raise NotImplementedError("Implementación pendiente en la siguiente Fase 4 (Audio).")
