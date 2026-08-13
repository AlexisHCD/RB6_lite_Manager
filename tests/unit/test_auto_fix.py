"""Unit tests for safe Health Check repairs."""

from __future__ import annotations

import pytest

from openbuds.application.auto_fix import ApplyAutoFixUseCase, AutoFixRequest
from openbuds.core.errors import OpenBudsError
from openbuds.domain.enums import CheckSeverity, EvidenceKind, HealthStatus
from openbuds.domain.models import CheckResult, HealthReport


class FakeServices:
    """User-service controller fake."""

    def __init__(self) -> None:
        self.units: list[tuple[str, ...]] = []

    def start(self, units: tuple[str, ...]) -> None:
        self.units.append(units)

    def is_active(self, _unit: str) -> bool:
        return True


class FakeAudioControl:
    """Runtime audio control fake."""

    def __init__(self) -> None:
        self.profiles: list[tuple[str, str]] = []

    def list_profiles(self, _device_address: str) -> tuple[str, ...]:
        return ("a2dp-sink",)

    def set_profile(self, device_address: str, profile_name: str) -> None:
        self.profiles.append((device_address, profile_name))


class FakeHealth:
    """Diagnostics dependency fake."""


def _report(*fixes: str) -> HealthReport:
    return HealthReport(
        overall_status=HealthStatus.WARNING,
        checks=tuple(
            CheckResult(
                check_id=f"check.{index}",
                label="Check",
                severity=CheckSeverity.WARNING,
                message="needs repair",
                auto_fix_available=True,
                auto_fix_id=fix_id,
                evidence=EvidenceKind.OBSERVED,
            )
            for index, fix_id in enumerate(fixes)
        ),
    )


def _use_case(
    *,
    audio: FakeAudioControl | None = None,
    services: FakeServices | None = None,
) -> ApplyAutoFixUseCase:
    return ApplyAutoFixUseCase(  # type: ignore[arg-type]
        FakeHealth(), audio_control=audio, services=services
    )


def test_available_fix_ids_are_unique_and_keep_report_order() -> None:
    use_case = _use_case()

    assert use_case.available_fix_ids(_report("start.audio", "profile.a2dp", "start.audio")) == (
        "start.audio",
        "profile.a2dp",
    )


def test_start_audio_delegates_to_user_services() -> None:
    services = FakeServices()

    result = _use_case(services=services).execute(AutoFixRequest("start.audio"))

    assert result == "unidades de audio de usuario iniciadas"
    assert services.units == [("pipewire", "wireplumber")]


def test_profile_a2dp_delegates_to_runtime_audio_control() -> None:
    audio = FakeAudioControl()

    result = _use_case(audio=audio).execute(AutoFixRequest("profile.a2dp", "00:11:22:33:44:55"))

    assert result == "perfil A2DP aplicado"
    assert audio.profiles == [("00:11:22:33:44:55", "a2dp-sink")]


def test_profile_a2dp_requires_a_connected_device() -> None:
    with pytest.raises(OpenBudsError, match="requiere dispositivo conectado"):
        _use_case(audio=FakeAudioControl()).execute(AutoFixRequest("profile.a2dp"))


def test_unknown_fix_is_rejected() -> None:
    with pytest.raises(OpenBudsError, match="auto-fix desconocido: no-existe"):
        _use_case().execute(AutoFixRequest("no-existe"))


def test_start_audio_requires_user_services() -> None:
    with pytest.raises(OpenBudsError):
        _use_case().execute(AutoFixRequest("start.audio"))
