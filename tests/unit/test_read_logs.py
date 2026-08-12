"""Unit tests for the read-logs use case."""

from __future__ import annotations

import pytest

from openbuds.application.read_logs import ReadLogsRequest, ReadLogsUseCase
from openbuds.domain.models import ServiceLogs


class FakeDiagnosticsRepository:
    """Minimal diagnostics fake for delegation tests."""

    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], int]] = []

    def read_logs(self, services: tuple[str, ...], lines: int) -> tuple[ServiceLogs, ...]:
        self.calls.append((services, lines))
        return (ServiceLogs("bluez", True, ("line",)),)


def test_read_logs_validates_and_delegates() -> None:
    repository = FakeDiagnosticsRepository()
    use_case = ReadLogsUseCase(repository)  # type: ignore[arg-type]
    request = ReadLogsRequest(("bluez", "pipewire"), 12)

    assert use_case.execute(request) == (ServiceLogs("bluez", True, ("line",)),)
    assert repository.calls == [(("bluez", "pipewire"), 12)]


@pytest.mark.parametrize("lines", [0, 201, True])
def test_read_logs_rejects_invalid_line_count(lines: object) -> None:
    repository = FakeDiagnosticsRepository()

    with pytest.raises(ValueError):
        ReadLogsUseCase(repository).execute(  # type: ignore[arg-type]
            ReadLogsRequest(("bluez",), lines)
        )

    assert repository.calls == []


def test_read_logs_rejects_empty_service_selection() -> None:
    repository = FakeDiagnosticsRepository()

    with pytest.raises(ValueError):
        ReadLogsUseCase(repository).execute(ReadLogsRequest((), 20))  # type: ignore[arg-type]

    assert repository.calls == []
