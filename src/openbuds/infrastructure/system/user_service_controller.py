"""Safe controller for user-level systemd services."""

from __future__ import annotations

import math
import subprocess
from typing import Any, Protocol, cast

from openbuds.core.errors import ServiceError
from openbuds.domain.interfaces import IUserServiceController
from openbuds.infrastructure.redaction import sanitize_display


class ServiceResult(Protocol):
    """Minimum result contract required from a systemctl executor."""

    returncode: int
    stdout: Any
    stderr: Any


class Executor(Protocol):
    """Callable contract for executing a systemctl command."""

    def __call__(self, argv: list[str], **kwargs: Any) -> ServiceResult:
        """Execute ``argv`` and return its process result."""
        ...


class UserServiceController(IUserServiceController):
    """Control only user systemd units, never system units or sudo."""

    def __init__(
        self,
        binary: str = "systemctl",
        timeout_seconds: float = 10.0,
        executor: Executor | None = None,
    ) -> None:
        """Create a controller after validating its executable and timeout."""
        if type(binary) is not str or not binary or "\x00" in binary:
            raise ValueError("invalid systemctl binary")
        if (
            type(timeout_seconds) not in (int, float)
            or timeout_seconds <= 0
            or not math.isfinite(float(timeout_seconds))
        ):
            raise ValueError("invalid systemctl timeout")

        self._binary = binary
        self._timeout_seconds = timeout_seconds
        self._executor = executor if executor is not None else cast(Executor, subprocess.run)

    def start(self, units: tuple[str, ...]) -> None:
        """Start the requested user units without invoking a shell."""
        self._validate_units(units)
        try:
            result = self._executor(
                [self._binary, "--user", "start", *units],
                capture_output=True,
                text=True,
                check=False,
                timeout=self._timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise ServiceError("tiempo de espera agotado al iniciar unidades de usuario") from exc
        except OSError as exc:
            raise ServiceError("systemctl no disponible") from exc

        if result.returncode == 0:
            return

        message = f"no se pudieron iniciar las unidades de usuario (código {result.returncode})"
        if isinstance(result.stderr, str):
            detail = sanitize_display(result.stderr).strip()
            if detail:
                message = f"{message}: {detail}"
        raise ServiceError(message)

    def is_active(self, unit: str) -> bool:
        """Return whether one user unit is active, reporting failures as false."""
        self._validate_unit(unit)
        try:
            result = self._executor(
                [self._binary, "--user", "is-active", unit],
                capture_output=True,
                text=True,
                check=False,
                timeout=self._timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0

    @classmethod
    def _validate_units(cls, units: tuple[str, ...]) -> None:
        if type(units) is not tuple or not units:
            raise ValueError("invalid user service units")
        for unit in units:
            cls._validate_unit(unit)

    @staticmethod
    def _validate_unit(unit: str) -> None:
        if type(unit) is not str or not unit or "\x00" in unit:
            raise ValueError("invalid user service unit")
