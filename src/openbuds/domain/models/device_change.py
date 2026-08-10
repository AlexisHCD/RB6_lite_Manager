"""Evento tipado de cambio de un dispositivo Bluetooth."""

from __future__ import annotations

from dataclasses import dataclass

from openbuds.domain.enums import DeviceChangeKind
from openbuds.domain.models.device import DeviceInfo


@dataclass(frozen=True, slots=True)
class DeviceChangeEvent:
    """Describe una aparición, actualización o desaparición de ``Device1``."""

    kind: DeviceChangeKind
    current: DeviceInfo | None
    previous: DeviceInfo | None

    def __post_init__(self) -> None:
        """Valida la combinación de estados exigida por ADR-0007."""
        if self.kind is DeviceChangeKind.ADDED:
            if self.current is None or self.previous is not None:
                raise ValueError("ADDED requiere current y previous=None")
            return

        if self.kind is DeviceChangeKind.UPDATED:
            if self.current is None or self.previous is None:
                raise ValueError("UPDATED requiere current y previous")
            if self.current.object_path != self.previous.object_path:
                raise ValueError("UPDATED requiere el mismo object_path")
            return

        if self.kind is DeviceChangeKind.REMOVED:
            if self.current is not None or self.previous is None:
                raise ValueError("REMOVED requiere current=None y previous")
            return

        raise ValueError(f"kind no válido: {self.kind!r}")
