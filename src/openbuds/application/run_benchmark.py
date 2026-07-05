"""Caso de uso: ejecutar un benchmark de calidad de enlace.

Estado: Fase 1 — contrato definido, sin implementación (Fase 5).
"""

from __future__ import annotations

from openbuds.domain.interfaces import IDiagnosticsRepository
from openbuds.domain.models import BenchmarkResult


class RunBenchmarkUseCase:
    """Delegado sobre el repositorio de diagnóstico para benchmarks."""

    def __init__(self, diagnostics_repo: IDiagnosticsRepository) -> None:
        self._diagnostics = diagnostics_repo

    def execute(self, device_address: str, duration_seconds: int = 10) -> BenchmarkResult:
        """Ejecuta un benchmark para el dispositivo dado."""
        raise NotImplementedError("Implementación diferida a Fase 5 (Diagnóstico).")
