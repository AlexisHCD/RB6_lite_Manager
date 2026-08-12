"""Safe, read-only access to relevant system and user journal logs."""

from __future__ import annotations

import math
import subprocess
from typing import Any, Final, Protocol, cast

from openbuds.infrastructure.redaction import sanitize_display


class JournalLogResult(Protocol):
    """Minimum result contract required from a ``journalctl`` executor."""

    returncode: int
    stdout: Any
    stderr: Any


class Executor(Protocol):
    """Callable contract for executing a journal command."""

    def __call__(self, argv: list[str], **kwargs: Any) -> JournalLogResult:
        """Execute ``argv`` and return its process result."""
        ...


_SUPPORTED_SERVICES: Final = frozenset({"bluez", "wireplumber", "pipewire"})
# Logical service name -> systemd unit (the BlueZ daemon unit is
# `bluetooth.service`, not `bluez.service`).
_UNIT_BY_SERVICE: Final = {
    "bluez": "bluetooth",
    "wireplumber": "wireplumber",
    "pipewire": "pipewire",
}
_NONZERO_ERROR = "servicio no disponible o sin permisos"


class JournalLogReader:
    """Read sanitized journal lines without exposing subprocess output.

    The system journal is tried first. For ``wireplumber`` and ``pipewire``, a
    failed system-unit query is retried with ``--user`` because Ubuntu 24.04
    normally runs those services in the user journal. Each returned journal
    line is sanitized and limited to 300 characters.
    """

    def __init__(
        self,
        binary: str = "journalctl",
        timeout_seconds: float = 10.0,
        executor: Executor | None = None,
    ) -> None:
        """Create a reader after validating its executable and timeout."""
        if type(binary) is not str or not binary or "\x00" in binary:
            raise ValueError("invalid journalctl binary")
        if (
            type(timeout_seconds) not in (int, float)
            or timeout_seconds <= 0
            or not math.isfinite(float(timeout_seconds))
        ):
            raise ValueError("invalid journalctl timeout")

        self._binary = binary
        self._timeout_seconds = timeout_seconds
        self._executor = executor if executor is not None else cast(Executor, subprocess.run)

    def read(self, service: str, lines: int) -> tuple[bool, str, str]:
        """Read and sanitize up to 200 journal lines for a supported service."""
        if type(service) is not str or service not in _SUPPORTED_SERVICES:
            raise ValueError("unsupported journal service")
        if type(lines) is not int or not 1 <= lines <= 200:
            raise ValueError("journal lines must be between 1 and 200")

        available, output, error, retryable = self._execute(self._command(service, lines))
        empty_system_unit = available and output.strip() in {"", "-- No entries --"}
        if service != "bluez" and empty_system_unit:
            return self._execute(self._command(service, lines, user=True))[:3]
        if available or service == "bluez" or not retryable:
            return available, output, error
        return self._execute(self._command(service, lines, user=True))[:3]

    def _command(self, service: str, lines: int, *, user: bool = False) -> list[str]:
        """Build one explicit, non-paginated journal command."""
        command = [self._binary]
        if user:
            command.append("--user")
        unit = _UNIT_BY_SERVICE[service]
        command.extend(["-u", unit, "-n", str(lines), "--no-pager", "-o", "short"])
        return command

    def _execute(self, argv: list[str]) -> tuple[bool, str, str, bool]:
        """Execute one attempt and return safe output plus retry eligibility."""
        try:
            result = self._executor(
                argv,
                capture_output=True,
                text=True,
                check=False,
                timeout=self._timeout_seconds,
            )
        except OSError:
            return False, "", "journalctl no disponible", False
        except subprocess.TimeoutExpired:
            return False, "", "journalctl excedió el tiempo límite", False

        if result.returncode != 0:
            return False, "", _NONZERO_ERROR, True
        if not isinstance(result.stdout, str):
            return False, "", _NONZERO_ERROR, False

        sanitized = "\n".join(
            sanitize_display(line, limit=300) for line in result.stdout.splitlines()
        )
        return True, sanitized, "", False
