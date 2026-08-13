"""Application use case for safe Health Check repairs."""

from __future__ import annotations

from dataclasses import dataclass

from openbuds.application.run_health_check import RunHealthCheckUseCase
from openbuds.core.errors import OpenBudsError
from openbuds.domain.enums import AutoFixId
from openbuds.domain.interfaces import (
    IAudioControlRepository,
    IDiagnosticsRepository,
    IUserServiceController,
)
from openbuds.domain.models import HealthReport


@dataclass(frozen=True, slots=True)
class AutoFixRequest:
    """Parameters for one approved Health Check repair."""

    fix_id: str
    device_address: str | None = None


class ApplyAutoFixUseCase:
    """Apply only explicitly supported, runtime-safe Health Check repairs."""

    def __init__(
        self,
        health: IDiagnosticsRepository | RunHealthCheckUseCase,
        audio_control: IAudioControlRepository | None = None,
        services: IUserServiceController | None = None,
    ) -> None:
        self._health = health
        self._audio_control = audio_control
        self._services = services

    @staticmethod
    def available_fix_ids(report: HealthReport) -> tuple[str, ...]:
        """Return unique available repair ids in report order."""
        available: list[str] = []
        seen: set[str] = set()
        for check in report.checks:
            if check.auto_fix_available and check.auto_fix_id and check.auto_fix_id not in seen:
                available.append(check.auto_fix_id)
                seen.add(check.auto_fix_id)
        return tuple(available)

    def execute(self, request: AutoFixRequest) -> str:
        """Apply one safe repair and return a user-readable result."""
        if request.fix_id == AutoFixId.START_AUDIO:
            if self._services is None:
                raise OpenBudsError("servicio de audio de usuario no disponible")
            self._services.start(("pipewire", "wireplumber"))
            return "unidades de audio de usuario iniciadas"

        if request.fix_id == AutoFixId.PROFILE_A2DP:
            if self._audio_control is None or request.device_address is None:
                raise OpenBudsError("requiere dispositivo conectado")
            self._audio_control.set_profile(request.device_address, "a2dp-sink")
            return "perfil A2DP aplicado"

        raise OpenBudsError(f"auto-fix desconocido: {request.fix_id}")
