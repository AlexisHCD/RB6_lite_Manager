"""Modelo de lectura de RSSI (``Device1.RSSI`` / ``Device1.TxPower``)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class RSSIReading:
    """Lectura puntual de potencia de señal recibida.

    Atributos:
        rssi_dbm: Intensidad de señal recibida en dBm (típicamente -100 a 0).
        tx_power_dbm: Potencia de transmisión reportada, si está disponible.
        timestamp: Momento de la lectura (UTC, consciente de zona horaria).
    """

    rssi_dbm: int | None
    timestamp: datetime
    tx_power_dbm: int | None = None

    def __post_init__(self) -> None:
        """Valida el signo del RSSI bluetooth (siempre <= 0 dBm)."""
        if self.rssi_dbm is not None and self.rssi_dbm > 0:
            # RSSI bluetooth clásico es siempre negativo; este guard protege
            # contra errores de mapeo desde BlueZ.
            raise ValueError(f"rssi_dbm bluetooth debería ser <= 0, recibido: {self.rssi_dbm}")
