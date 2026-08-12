"""Unit tests for runtime PipeWire profile control."""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from openbuds.core.errors import ProfileUnavailableError
from openbuds.infrastructure.pipewire.pipewire_control_repository import (
    PipeWireControlRepository,
)


def _device_payload(address: str = "00:11:22:33:44:55", device_id: int = 42) -> str:
    return json.dumps(
        [
            {
                "id": device_id,
                "type": "PipeWire:Interface:Device",
                "info": {
                    "props": {
                        "device.api": "bluez5",
                        "api.bluez5.address": address,
                    }
                },
            }
        ]
    )


@dataclass
class FakeDumpRunner:
    payload: str
    calls: int = 0

    def dump(self) -> str:
        self.calls += 1
        return self.payload


@dataclass
class FakeCliRunner:
    output: str
    calls: list[int] | None = None

    def __post_init__(self) -> None:
        self.calls = []

    def enum_params(self, device_id: int) -> str:
        assert self.calls is not None
        self.calls.append(device_id)
        return self.output


@dataclass
class FakeWpctl:
    calls: list[tuple[int, int]] | None = None

    def __post_init__(self) -> None:
        self.calls = []

    def set_profile(self, device_id: int, profile_index: int) -> None:
        assert self.calls is not None
        self.calls.append((device_id, profile_index))


def test_list_profiles_resolves_device_id_and_returns_names() -> None:
    cli_runner = FakeCliRunner("index:0 id:0 name:off\nindex:2 name:a2dp-sink")
    repository = PipeWireControlRepository(
        FakeDumpRunner(_device_payload()), cli_runner, FakeWpctl()
    )

    assert repository.list_profiles("00_11_22_33_44_55") == ("off", "a2dp-sink")
    assert cli_runner.calls == [42]


def test_list_profiles_returns_empty_for_unknown_device() -> None:
    cli_runner = FakeCliRunner("index:0 name:off")
    repository = PipeWireControlRepository(FakeDumpRunner("[]"), cli_runner, FakeWpctl())

    assert repository.list_profiles("00:11:22:33:44:55") == ()
    assert cli_runner.calls == []


def test_set_profile_uses_resolved_id_and_profile_index() -> None:
    cli_runner = FakeCliRunner("index:0 id:0 name:off\nindex:4 id:4 name:a2dp-sink")
    wpctl = FakeWpctl()
    repository = PipeWireControlRepository(FakeDumpRunner(_device_payload()), cli_runner, wpctl)

    repository.set_profile("00:11:22:33:44:55", "a2dp-sink")

    assert cli_runner.calls == [42]
    assert wpctl.calls == [(42, 4)]


def test_set_profile_rejects_profile_not_offered() -> None:
    repository = PipeWireControlRepository(
        FakeDumpRunner(_device_payload()),
        FakeCliRunner("index:0 name:off"),
        FakeWpctl(),
    )

    with pytest.raises(ProfileUnavailableError, match="no ofrecido"):
        repository.set_profile("00:11:22:33:44:55", "a2dp-sink")


def test_set_profile_rejects_device_without_audio_card() -> None:
    repository = PipeWireControlRepository(FakeDumpRunner("[]"), FakeCliRunner(""), FakeWpctl())

    with pytest.raises(ProfileUnavailableError, match="tarjeta de audio"):
        repository.set_profile("00:11:22:33:44:55", "a2dp-sink")
