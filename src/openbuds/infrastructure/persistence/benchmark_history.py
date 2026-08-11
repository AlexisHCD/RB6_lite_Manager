"""Persistencia del historial de benchmarks.

Estado: Etapa 0 — esqueleto. Historial previsto para una etapa posterior.
"""

from __future__ import annotations

from pathlib import Path

from openbuds.domain.models import BenchmarkResult


class BenchmarkHistory:
    """Almacena y recupera resultados de benchmarks.

    Estado: Etapa 0 — sin implementación.
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def append(self, result: BenchmarkResult) -> None:
        """Añade un resultado al historial."""
        raise NotImplementedError("Historial previsto para una etapa posterior.")

    def list(self, limit: int = 50) -> list[BenchmarkResult]:
        """Devuelve los últimos ``limit`` resultados (más recientes primero)."""
        raise NotImplementedError("Historial previsto para una etapa posterior.")
