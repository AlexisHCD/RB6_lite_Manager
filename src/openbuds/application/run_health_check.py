"""Use case for running a complete read-only system Health Check."""

from __future__ import annotations

from openbuds.domain.interfaces import IDiagnosticsRepository
from openbuds.domain.models import HealthReport


class RunHealthCheckUseCase:
    """Thin delegate over the diagnostic repository.

    Kept separate so application logic can grow without coupling the repository.
    """

    def __init__(self, diagnostics_repo: IDiagnosticsRepository) -> None:
        self._diagnostics = diagnostics_repo

    def execute(self) -> HealthReport:
        """Run the read-only Health Check; every datum is evidence-labelled."""
        return self._diagnostics.run_health_check()
