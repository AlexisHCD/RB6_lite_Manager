"""Safe subprocess runner for ``pw-cli`` profile inspection."""

from __future__ import annotations

import math
import subprocess
from typing import Any, Protocol, cast

from openbuds.core.errors import PipeWireUnavailableError


class PwCliResult(Protocol):
    """Minimum result contract required from a ``pw-cli`` executor."""

    returncode: int
    stdout: Any
    stderr: Any


class Executor(Protocol):
    """Callable contract for executing a subprocess command."""

    def __call__(self, argv: list[str], **kwargs: Any) -> PwCliResult:
        """Execute ``argv`` and return its process result."""
        ...


class PwCliRunner:
    """Run the read-only ``pw-cli enum-params`` command safely."""

    def __init__(
        self,
        binary: str = "pw-cli",
        timeout_seconds: int | float = 5.0,
        executor: Executor | None = None,
    ) -> None:
        """Create a runner after validating its executable and timeout."""
        if type(binary) is not str or not binary or "\x00" in binary:
            raise ValueError("invalid pw-cli binary")
        if (
            type(timeout_seconds) not in (int, float)
            or timeout_seconds <= 0
            or not math.isfinite(float(timeout_seconds))
        ):
            raise ValueError("invalid pw-cli timeout")

        self._binary = binary
        self._timeout_seconds = timeout_seconds
        self._executor = executor if executor is not None else cast(Executor, subprocess.run)

    def enum_params(self, device_id: int) -> str:
        """Return the runtime ``EnumProfile`` parameters for a device."""
        if type(device_id) is not int or device_id < 0:
            raise ValueError("invalid PipeWire device id")
        try:
            result = self._executor(
                [self._binary, "enum-params", str(device_id), "EnumProfile"],
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
