"""Pruebas unitarias del repositorio PipeWire basado en ``pw-dump``."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

import pytest

from openbuds.core.errors import (
    PipeWireParseError,
    PipeWireUnavailableError,
    WirePlumberUnavailableError,
)
from openbuds.domain.enums import BluetoothProfile, CodecType
from openbuds.domain.models import BluetoothAudioNode
from openbuds.infrastructure.pipewire import pipewire_repository as repository_module
from openbuds.infrastructure.pipewire.pipewire_repository import PipeWireRepository


class FakeRunner:
    """Runner determinista para aislar el repositorio del sistema."""

    def __init__(
        self,
        payloads: Iterable[str],
        error: BaseException | None = None,
    ) -> None:
        self._payloads = iter(payloads)
        self.error = error
        self.dump_calls = 0

    def __bool__(self) -> bool:
        return False

    def dump(self) -> str:
        self.dump_calls += 1
        if self.error is not None:
            raise self.error
        return next(self._payloads)


class FakeWpctl:
    """Deterministic ``wpctl`` adapter substitute."""

    def __init__(self, output: str = "", error: BaseException | None = None) -> None:
        self.output = output
        self.error = error
        self.target: str | None = None

    def inspect(self, target: str) -> str:
        self.target = target
        if self.error is not None:
            raise self.error
        return self.output


def _node(node_id: int, node_name: str, media_class: str = "Audio/Sink") -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "PipeWire:Interface:Node",
        "info": {
            "props": {
                "media.class": media_class,
                "node.name": node_name,
                "api.bluez5.profile": "a2dp-sink",
                "api.bluez5.codec": "sbc",
                "api.bluez5.address": "00:11:22:33:44:55",
                "enabled": True,
            }
        },
    }


def _payload(*nodes: dict[str, Any]) -> str:
    return json.dumps(list(nodes))


def test_list_nodes_uses_injected_falsy_runner_and_normalizes_payload() -> None:
    runner = FakeRunner(
        [
            _payload(
                _node(7, "bluez_output.AA"),
                _node(3, "bluez_input.AA", "Audio/Source"),
            )
        ]
    )

    result = PipeWireRepository(runner).list_bluetooth_audio_nodes()

    assert result == [
        BluetoothAudioNode("bluez_input.AA", "Audio/Source", "a2dp-sink", "sbc", None),
        BluetoothAudioNode("bluez_output.AA", "Audio/Sink", "a2dp-sink", "sbc", None),
    ]
    assert runner.dump_calls == 1


def test_default_runner_is_created_once_and_used(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = FakeRunner(["[]"])
    factory_calls = 0

    def factory() -> FakeRunner:
        nonlocal factory_calls
        factory_calls += 1
        return runner

    monkeypatch.setattr(repository_module, "PwDumpRunner", factory)

    repository = PipeWireRepository()

    assert repository.list_bluetooth_audio_nodes() == []
    assert factory_calls == 1
    assert runner.dump_calls == 1


def test_list_nodes_dumps_fresh_data_without_cache() -> None:
    runner = FakeRunner(
        [
            _payload(_node(1, "bluez_output.FIRST")),
            _payload(_node(2, "bluez_output.SECOND")),
        ]
    )
    repository = PipeWireRepository(runner)

    first = repository.list_bluetooth_audio_nodes()
    second = repository.list_bluetooth_audio_nodes()

    assert first[0].node_name == "bluez_output.FIRST"
    assert second == [
        BluetoothAudioNode("bluez_output.SECOND", "Audio/Sink", "a2dp-sink", "sbc", None)
    ]
    assert runner.dump_calls == 2


def test_empty_payload_returns_empty_list() -> None:
    runner = FakeRunner(["[]"])

    assert PipeWireRepository(runner).list_bluetooth_audio_nodes() == []


def test_invalid_json_raises_exact_parse_error() -> None:
    runner = FakeRunner(["not json"])

    with pytest.raises(PipeWireParseError) as raised:
        PipeWireRepository(runner).list_bluetooth_audio_nodes()

    assert type(raised.value) is PipeWireParseError
    assert str(raised.value) == "JSON de pw-dump inválido"


def test_runner_unavailable_error_is_propagated_identically() -> None:
    error = PipeWireUnavailableError("runner failed")
    runner = FakeRunner([], error=error)

    with pytest.raises(PipeWireUnavailableError) as raised:
        PipeWireRepository(runner).list_bluetooth_audio_nodes()

    assert raised.value is error
    assert raised.value.__cause__ is error.__cause__


def test_default_sink_returns_observed_name() -> None:
    wpctl = FakeWpctl(
        'id 141, type PipeWire:Interface:Node\n  * node.name = "bluez_output.00_11_22_33_44_55.1"\n'
    )

    repository = PipeWireRepository(FakeRunner([]), wpctl)

    assert repository.get_default_audio_sink() == "bluez_output.00_11_22_33_44_55.1"
    assert wpctl.target == "@DEFAULT_AUDIO_SINK@"


def test_default_sink_parses_indented_property_lines() -> None:
    wpctl = FakeWpctl(
        "id 48, type PipeWire:Interface:Node\n"
        '    node.name = "alsa_output.pci-0000_00_1f.3.analog-stereo"\n'
    )

    assert (
        PipeWireRepository(FakeRunner([]), wpctl).get_default_audio_sink()
        == "alsa_output.pci-0000_00_1f.3.analog-stereo"
    )


def test_default_sink_returns_none_without_node_name() -> None:
    wpctl = FakeWpctl('object.path = "x"\n')

    assert PipeWireRepository(FakeRunner([]), wpctl).get_default_audio_sink() is None


def test_default_sink_returns_none_when_wireplumber_is_unavailable() -> None:
    wpctl = FakeWpctl(error=WirePlumberUnavailableError("unavailable"))

    assert PipeWireRepository(FakeRunner([]), wpctl).get_default_audio_sink() is None


def test_default_wpctl_is_created() -> None:
    assert PipeWireRepository(FakeRunner([]))._wpctl is not None


def test_active_codec_maps_observed_profile_and_codec() -> None:
    repository = PipeWireRepository(FakeRunner([_payload(_node(1, "bluez_output.X"))]))

    result = repository.get_active_codec("00_11_22_33_44_55")

    assert result is not None
    assert result.codec is CodecType.SBC
    assert result.profile is BluetoothProfile.A2DP
    assert result.verified is True
