"""Contrato del repositorio de diagnóstico (Health Check + Benchmark).

Implementaciones de referencia:
  - ``openbuds.infrastructure.system.environment_detector`` (parte de Health Check).
  - Módulo de benchmark (Fase 5).
"""

from __future__ import annotations

from openbuds.domain.models import BenchmarkResult, HealthReport, SystemInfo


class IDiagnosticsRepository:
    """Provee diagnóstico del sistema: Health Check y Benchmark.

    Health Check revisa el estado del stack completo (BlueZ, PipeWire,
    WirePlumber, servicios, permisos, codecs, adaptador) y genera
    recomendaciones. Las reparaciones automáticas solo se ofrecen cuando son
    completamente seguras.

    Benchmark mide la calidad del enlace activo (RSSI, jitter, latencia,
    packet loss, retransmisiones). Algunas métricas pueden no ser accesibles
    desde el espacio de usuario sin captura HCI privilegiada.
    """

    def run_health_check(self) -> HealthReport:
        """Ejecuta un Health Check completo y devuelve un informe."""
        raise NotImplementedError

    def detect_system(self) -> SystemInfo:
        """Detecta el entorno del sistema (SO, versiones del stack, adaptador)."""
        raise NotImplementedError

    def run_benchmark(self, device_address: str, duration_seconds: int = 10) -> BenchmarkResult:
        """Ejecuta un benchmark de calidad de enlace para el dispositivo dado.

        Args:
            device_address: Dirección MAC del dispositivo a evaluar.
            duration_seconds: Duración de la sesión de muestreo.

        """
        raise NotImplementedError
