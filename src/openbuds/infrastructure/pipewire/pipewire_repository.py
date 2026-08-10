"""Implementación de ``IAudioRepository`` sobre PipeWire (subprocess pw-dump/wpctl).

Estado: Fase 1 — esqueleto que cumple la interfaz. Implementación en Fase 3/4.

Justificación (ADR-0003): no existe binding Python oficial de PipeWire. La
inspección fiable se hace parseando ``pw-dump`` (JSON) y ``wpctl inspect``.
"""

from __future__ import annotations

from openbuds.domain.interfaces import IAudioRepository
from openbuds.domain.models import CodecInfo


class PipeWireRepository(IAudioRepository):
    """Repositorio de audio basado en las CLI de PipeWire/WirePlumber.

    Estado: Fase 1 — sin implementación.
    """

    def get_active_codec(self, device_address: str) -> CodecInfo | None:
        raise NotImplementedError("Fase 3/4 (Audio).")

    def list_bluetooth_audio_nodes(self) -> list[dict[str, str]]:
        raise NotImplementedError("Fase 3/4 (Audio).")

    def get_default_audio_sink(self) -> str | None:
        raise NotImplementedError("Fase 3/4 (Audio).")
