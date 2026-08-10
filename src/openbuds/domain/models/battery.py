"""Modelo de nivel de batería (``org.bluez.Battery1``)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BatteryLevel:
    """Nivel de batería de un dispositivo Bluetooth.

    Corresponde a ``org.bluez.Battery1``, que solo aparece si el dispositivo
    expone batería (GATT Battery Service UUID 0x180F, o vía comandos AT de
    HFP/AVRCP).

    Atributos:
        percentage: Nivel de batería (0-100). ``None`` si no está disponible.
        source: Origen del informe. Valores observados:
            "GATT Battery Service", "HFP", "AVRCP", etc.
    """

    percentage: int | None
    source: str = ""

    def __post_init__(self) -> None:
        """Valida el invariante de rango del porcentaje de batería."""
        if self.percentage is not None and not (0 <= self.percentage <= 100):
            raise ValueError(f"percentage debe estar en [0, 100], recibido: {self.percentage}")
