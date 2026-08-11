"""Adaptador de solo lectura para la CLI ``wpctl`` (Incremento 1)."""

from __future__ import annotations

import math
import subprocess
from typing import Any, Protocol

from openbuds.core.errors import WirePlumberUnavailableError


class WpctlResult(Protocol):
    """Resultado mínimo requerido por el executor de ``wpctl``."""

    returncode: int
    stdout: Any
    stderr: Any


class Executor(Protocol):
    """Callable compatible con ``subprocess.run``."""

    def __call__(self, argv: list[str], **kwargs: Any) -> WpctlResult:
        """Ejecuta ``wpctl`` y devuelve un resultado compatible."""
        ...


class WpctlAdapter:
    """Ejecuta consultas seguras y frescas contra ``wpctl``.

    Incremento 1 es estrictamente de solo lectura. Las operaciones mutadoras
    permanecen sin implementar hasta disponer de backup y rollback.
    """

    def __init__(
        self,
        binary: str = "wpctl",
        timeout_seconds: int | float = 5.0,
        executor: Executor | None = None,
    ) -> None:
        if type(binary) is not str or not binary or "\x00" in binary:
            raise ValueError("invalid wpctl configuration")
        if (
            type(timeout_seconds) not in (int, float)
            or timeout_seconds <= 0
            or not math.isfinite(timeout_seconds)
        ):
            raise ValueError("invalid wpctl configuration")

        self._binary = binary
        self._timeout_seconds = timeout_seconds
        self._executor = executor if executor is not None else subprocess.run

    def _run(self, args: list[str]) -> str:
        """Ejecuta una consulta y devuelve stdout sin modificarlo."""
        try:
            result = self._executor(
                [self._binary, *args],
                capture_output=True,
                text=True,
                check=False,
                timeout=self._timeout_seconds,
            )
        except (subprocess.TimeoutExpired, OSError) as error:
            raise WirePlumberUnavailableError("wpctl is unavailable") from error

        if result.returncode != 0 or type(result.stdout) is not str:
            raise WirePlumberUnavailableError("wpctl is unavailable")
        return result.stdout

    def status(self) -> str:
        """Devuelve exactamente la salida de ``wpctl status``."""
        return self._run(["status"])

    def inspect(self, object_id: int | str) -> str:
        """Devuelve exactamente la salida de ``wpctl inspect`` para un objeto."""
        if type(object_id) is int and object_id >= 0:
            target = str(object_id)
        elif type(object_id) is str and object_id == "@DEFAULT_AUDIO_SINK@":
            target = object_id
        else:
            raise ValueError("invalid wpctl inspect target")
        return self._run(["inspect", target])

    def set_profile(self, device_id: int, profile_index: int) -> None:
        """No implementado: el Incremento 1 no permite mutaciones."""
        raise NotImplementedError("WpctlAdapter Incremento 1 is read-only")

    def restart_service(self) -> None:
        """No implementado: el Incremento 1 no permite mutaciones."""
        raise NotImplementedError("WpctlAdapter Incremento 1 is read-only")
