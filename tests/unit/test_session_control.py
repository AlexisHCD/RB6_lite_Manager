"""Unit tests for session control use cases."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from openbuds.application.session_control import (
    ConnectDeviceRequest,
    ConnectDeviceUseCase,
    DisconnectDeviceRequest,
    DisconnectDeviceUseCase,
    SetAudioProfileRequest,
    SetAudioProfileUseCase,
)
from openbuds.core.errors import ProfileUnavailableError
from openbuds.domain.enums import BluetoothProfile


@dataclass
class FakeBluetoothRepository:
    calls: list[tuple[str, str]] | None = None

    def __post_init__(self) -> None:
        self.calls = []

    def connect(self, device_path: str) -> None:
        assert self.calls is not None
        self.calls.append(("connect", device_path))

    def disconnect(self, device_path: str) -> None:
        assert self.calls is not None
        self.calls.append(("disconnect", device_path))


@dataclass
class FakeAudioRepository:
    profiles: tuple[str, ...]
    listed: list[str] | None = None
    applied: list[tuple[str, str]] | None = None

    def __post_init__(self) -> None:
        self.listed = []
        self.applied = []

    def list_profiles(self, device_address: str) -> tuple[str, ...]:
        assert self.listed is not None
        self.listed.append(device_address)
        return self.profiles

    def set_profile(self, device_address: str, profile_name: str) -> None:
        assert self.applied is not None
        self.applied.append((device_address, profile_name))


def test_connect_and_disconnect_delegate_to_bluetooth_repository() -> None:
    repository = FakeBluetoothRepository()

    ConnectDeviceUseCase(repository).execute(ConnectDeviceRequest("/device"))
    DisconnectDeviceUseCase(repository).execute(DisconnectDeviceRequest("/device"))

    assert repository.calls == [("connect", "/device"), ("disconnect", "/device")]


def test_a2dp_maps_to_a2dp_sink() -> None:
    repository = FakeAudioRepository(("off", "a2dp-sink"))

    result = SetAudioProfileUseCase(repository).execute(
        SetAudioProfileRequest("00:11:22:33:44:55", BluetoothProfile.A2DP)
    )

    assert result == "a2dp-sink"
    assert repository.applied == [("00:11:22:33:44:55", "a2dp-sink")]


def test_hfp_prefers_msbc() -> None:
    repository = FakeAudioRepository(("headset-head-unit", "headset-head-unit-msbc"))

    result = SetAudioProfileUseCase(repository).execute(
        SetAudioProfileRequest("00:11:22:33:44:55", BluetoothProfile.HFP)
    )

    assert result == "headset-head-unit-msbc"


def test_hfp_falls_back_to_generic_headset_profile() -> None:
    repository = FakeAudioRepository(("off", "headset-head-unit"))

    result = SetAudioProfileUseCase(repository).execute(
        SetAudioProfileRequest("00:11:22:33:44:55", BluetoothProfile.HFP)
    )

    assert result == "headset-head-unit"


def test_hfp_without_offered_profile_is_unavailable() -> None:
    repository = FakeAudioRepository(("off", "a2dp-sink"))

    with pytest.raises(ProfileUnavailableError, match="no ofrece"):
        SetAudioProfileUseCase(repository).execute(
            SetAudioProfileRequest("00:11:22:33:44:55", BluetoothProfile.HFP)
        )


def test_unsupported_profile_is_rejected() -> None:
    repository = FakeAudioRepository(())

    with pytest.raises(ValueError):
        SetAudioProfileUseCase(repository).execute(
            SetAudioProfileRequest("00:11:22:33:44:55", BluetoothProfile.HSP)
        )
