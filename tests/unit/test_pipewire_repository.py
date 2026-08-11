"""Pruebas unitarias del repositorio PipeWire basado en ``pw-dump``."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

import pytest

from openbuds.core.errors import PipeWireParseError, PipeWireUnavailableError
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


def _node(node_id: int, node_name: str, media_class: str = "Audio/Sink") -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "PipeWire:Interface:Node",
        "info": {
            "props": {
                "media.class": media_class,
                "node.name": node_name,
                "device.profile": "a2dp-sink",
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
        {
            "object.id": "3",
            "media.class": "Audio/Source",
            "node.name": "bluez_input.AA",
            "device.profile": "a2dp-sink",
            "enabled": "true",
        },
        {
            "object.id": "7",
            "media.class": "Audio/Sink",
            "node.name": "bluez_output.AA",
            "device.profile": "a2dp-sink",
            "enabled": "true",
        },
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


def test_list_nodes_dumps_fresh_data_without_cache_and_returns_independent_dicts() -> None:
    runner = FakeRunner(
        [
            _payload(_node(1, "bluez_output.FIRST")),
            _payload(_node(2, "bluez_output.SECOND")),
        ]
    )
    repository = PipeWireRepository(runner)

    first = repository.list_bluetooth_audio_nodes()
    first[0]["mutated"] = "only-first"
    second = repository.list_bluetooth_audio_nodes()

    assert first[0]["node.name"] == "bluez_output.FIRST"
    assert "mutated" not in second[0]
    assert second == [
        {
            "object.id": "2",
            "media.class": "Audio/Sink",
            "node.name": "bluez_output.SECOND",
            "device.profile": "a2dp-sink",
            "enabled": "true",
        }
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


@pytest.mark.parametrize(
    "query",
    [
        lambda repository: repository.get_active_codec("AA:BB:CC:DD:EE:FF"),
        lambda repository: repository.get_default_audio_sink(),
    ],
)
def test_unimplemented_queries_remain_explicit(query: Any) -> None:
    with pytest.raises(NotImplementedError):
        query(PipeWireRepository(FakeRunner([])))
