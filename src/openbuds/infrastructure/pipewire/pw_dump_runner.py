"""Safe subprocess runner for the ``pw-dump`` PipeWire command."""

from __future__ import annotations

import math
import subprocess
from typing import Any, Protocol, cast

from openbuds.core.errors import PipeWireUnavailableError


class PwDumpResult(Protocol):
    """Minimum result contract required from a ``pw-dump`` executor."""

    returncode: int
    stdout: Any
    stderr: Any


class Executor(Protocol):
    """Callable contract for executing a subprocess command."""

    def __call__(self, argv: list[str], **kwargs: Any) -> PwDumpResult:
        """Execute ``argv`` and return its process result."""
        ...


class PwDumpRunner:
    """Run ``pw-dump`` without exposing subprocess details to callers."""

    def __init__(
        self,
        binary: str = "pw-dump",
        timeout_seconds: int | float = 5.0,
        executor: Executor | None = None,
    ) -> None:
        """Create a runner after validating its executable and timeout."""
        if type(binary) is not str or not binary or "\x00" in binary:
            raise ValueError("invalid pw-dump binary")
        if (
            type(timeout_seconds) not in (int, float)
            or timeout_seconds <= 0
            or not math.isfinite(float(timeout_seconds))
        ):
            raise ValueError("invalid pw-dump timeout")

        self._binary = binary
        self._timeout_seconds = timeout_seconds
        self._executor = executor if executor is not None else cast(Executor, subprocess.run)

    def dump(self) -> str:
        """Return the exact textual output of a successful ``pw-dump`` call.

        Raises:
            PipeWireUnavailableError: If the command cannot run, fails, or
                returns non-text output.

        """
        try:
            result = self._executor(
                [self._binary, "--no-colors"],
                capture_output=True,
                text=True,
                check=False,
                timeout=self._timeout_seconds,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            raise PipeWireUnavailableError("PipeWire unavailable") from exc

        if result.returncode != 0 or not isinstance(result.stdout, str):
            raise PipeWireUnavailableError("PipeWire unavailable")
        return result.stdout
