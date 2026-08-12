"""Use case for reading sanitized diagnostic logs."""

from __future__ import annotations

from dataclasses import dataclass

from openbuds.domain.interfaces import IDiagnosticsRepository
from openbuds.domain.models import ServiceLogs


@dataclass(frozen=True, slots=True)
class ReadLogsRequest:
    """Parameters for a read-only log query."""

    services: tuple[str, ...]
    lines: int


class ReadLogsUseCase:
    """Validate log query parameters and delegate to diagnostics."""

    def __init__(self, diagnostics_repo: IDiagnosticsRepository) -> None:
        self._diagnostics = diagnostics_repo

    def execute(self, request: ReadLogsRequest) -> tuple[ServiceLogs, ...]:
        """Read logs for the requested services."""
        if type(request.lines) is not int or not 1 <= request.lines <= 200:
            raise ValueError("log lines must be between 1 and 200")
        if not request.services:
            raise ValueError("at least one log service is required")
        return self._diagnostics.read_logs(request.services, request.lines)
