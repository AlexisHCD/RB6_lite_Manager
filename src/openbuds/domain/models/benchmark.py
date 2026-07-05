"""Modelos de benchmark de calidad de enlace Bluetooth."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from openbuds.domain.enums import BluetoothProfile
from openbuds.domain.models.codec import CodecInfo


@dataclass(frozen=True, slots=True)
class BenchmarkSample:
    """Muestra puntual de métricas de enlace para un dispositivo.

    Algunos campos pueden ser ``None`` si la métrica no es medible desde el
    espacio de usuario sin captura HCI privilegiada (ver docs/RESEARCH_LIMITS.md).

    Atributos:
        timestamp: Momento de la muestra (UTC).
        rssi_dbm: Potencia de señal recibida.
        jitter_ms: Variación de latencia estimada en milisegundos.
        latency_ms: Latencia estimada unidireccional en milisegundos.
        packet_loss_pct: Porcentaje de paquetes perdidos (0-100).
        retransmissions: Número de retransmisiones observadas, si disponible.
    """

    timestamp: datetime
    rssi_dbm: int | None = None
    jitter_ms: float | None = None
    latency_ms: float | None = None
    packet_loss_pct: float | None = None
    retransmissions: int | None = None


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """Resultado agregado de una sesión de benchmark.

    Atributos:
        device_address: MAC del dispositivo evaluado.
        started_at: Inicio de la sesión (UTC).
        ended_at: Fin de la sesión (UTC).
        codec: Códec activo durante la medición.
        profile: Perfil Bluetooth activo durante la medición.
        samples: Muestras individuales recolectadas.
        quality_score: Puntuación estimada de calidad (0-100), heurística.
    """

    device_address: str
    started_at: datetime
    ended_at: datetime
    codec: CodecInfo
    profile: BluetoothProfile
    samples: tuple[BenchmarkSample, ...] = field(default_factory=tuple)
    quality_score: int | None = None

    def __post_init__(self) -> None:
        """Valida el invariante de rango de la puntuación de calidad."""
        if self.quality_score is not None and not (0 <= self.quality_score <= 100):
            raise ValueError(
                f"quality_score debe estar en [0, 100], recibido: {self.quality_score}"
            )
