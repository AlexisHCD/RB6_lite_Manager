"""Caso de uso: ejecutar un Health Check completo del sistema.

Estado: Etapa 0 — contrato definido, sin implementación; pendiente de la Etapa 4.
"""

from __future__ import annotations

from openbuds.domain.interfaces import IDiagnosticsRepository
from openbuds.domain.models import HealthReport


class RunHealthCheckUseCase:
    """Delegado fino sobre el repositorio de diagnóstico.

    Se mantiene como caso de uso aparte para poder añadir lógica de aplicación
    (caching, publicación de eventos, reglas de auto-fix) sin acoplar el repo.
    """

    def __init__(self, diagnostics_repo: IDiagnosticsRepository) -> None:
        self._diagnostics = diagnostics_repo

    def execute(self) -> HealthReport:
        """Ejecuta el Health Check y devuelve el informe."""
        raise NotImplementedError("Implementación pendiente de la Etapa 4 (Health Check).")
