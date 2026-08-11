"""Pruebas unitarias del adaptador seguro de ``wpctl``."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Any

import pytest

from openbuds.core.errors import WirePlumberUnavailableError
from openbuds.infrastructure.wireplumber.wpctl_adapter import WpctlAdapter


@dataclass(frozen=True)
class FakeWpctlResult:
    returncode: int
    stdout: Any
    stderr: Any


@dataclass
class RecordingExecutor:
    result: FakeWpctlResult | None = None
    error: BaseException | None = None
    falsy: bool = False
    calls: list[tuple[list[str], dict[str, Any]]] = field(default_factory=list)

    def __call__(self, argv: list[str], **kwargs: Any) -> FakeWpctlResult:
        self.calls.append((argv, kwargs))
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result

    def __bool__(self) -> bool:
        return not self.falsy


EXPECTED_KWARGS = {"capture_output": True, "text": True, "check": False, "timeout": 3.5}


def test_status_uses_exact_command_kwargs_and_stdout() -> None:
    executor = RecordingExecutor(FakeWpctlResult(0, "  exact output\n", "ignored"))
    adapter = WpctlAdapter(binary="/opt/my tools/wpctl", timeout_seconds=3.5, executor=executor)
    assert adapter.status() == "  exact output\n"
    assert executor.calls == [
        (["/opt/my tools/wpctl", "status"], EXPECTED_KWARGS),
    ]


@pytest.mark.parametrize(
    ("target", "target_text"),
    [(42, "42"), ("@DEFAULT_AUDIO_SINK@", "@DEFAULT_AUDIO_SINK@")],
)
def test_inspect_accepts_id_and_default_sink_alias(target: int | str, target_text: str) -> None:
    executor = RecordingExecutor(FakeWpctlResult(0, "inspection", ""))

    assert WpctlAdapter(executor=executor).inspect(target) == "inspection"
    assert executor.calls[0][0] == ["wpctl", "inspect", target_text]


@pytest.mark.parametrize("target", [True, -1, "1; rm -rf /"])
def test_invalid_inspect_target_is_rejected_before_execution(target: object) -> None:
    executor = RecordingExecutor(error=AssertionError("executor must not be called"))
    with pytest.raises(ValueError):
        WpctlAdapter(executor=executor).inspect(target)  # type: ignore[arg-type]

    assert executor.calls == []


@pytest.mark.parametrize(
    ("config", "value"),
    [
        ("binary", ""),
        ("binary", "wpctl\x00x"),
        ("binary", None),
        ("timeout_seconds", 0),
        ("timeout_seconds", float("nan")),
        ("timeout_seconds", float("inf")),
        ("timeout_seconds", True),
    ],
)
def test_invalid_configuration_is_rejected(config: str, value: object) -> None:
    with pytest.raises(ValueError):
        WpctlAdapter(**{config: value})  # type: ignore[arg-type]


def test_falsy_executor_is_preserved() -> None:
    executor = RecordingExecutor(FakeWpctlResult(0, "ok", ""), falsy=True)

    assert not executor
    assert WpctlAdapter(executor=executor).status() == "ok"
    assert len(executor.calls) == 1


@pytest.mark.parametrize(
    "error",
    [OSError("os failure"), subprocess.TimeoutExpired(["wpctl"], 5)],
)
def test_executor_failures_are_wrapped_with_cause(error: BaseException) -> None:
    executor = RecordingExecutor(error=error)
    with pytest.raises(WirePlumberUnavailableError) as raised:
        WpctlAdapter(executor=executor).status()

    assert raised.value.__cause__ is error


def test_nonzero_result_does_not_leak_sensitive_data() -> None:
    binary = "/secret/path/wpctl"
    stdout = "stdout secret"
    stderr = "MAC=AA:BB:CC:DD:EE:FF"
    adapter = WpctlAdapter(
        binary=binary,
        executor=RecordingExecutor(FakeWpctlResult(7, stdout, stderr)),
    )

    with pytest.raises(WirePlumberUnavailableError) as raised:
        adapter.status()

    message = str(raised.value)
    assert all(secret not in message for secret in (binary, stdout, stderr))


def test_non_string_stdout_is_unavailable() -> None:
    adapter = WpctlAdapter(executor=RecordingExecutor(FakeWpctlResult(0, b"bytes", "")))

    with pytest.raises(WirePlumberUnavailableError):
        adapter.status()


def test_unexpected_runtime_error_is_propagated() -> None:
    error = RuntimeError("fake programming failure")
    adapter = WpctlAdapter(executor=RecordingExecutor(error=error))

    with pytest.raises(RuntimeError) as raised:
        adapter.status()

    assert raised.value is error


@pytest.mark.parametrize("method", ["set_profile", "restart_service"])
def test_mutating_methods_are_not_implemented_or_executed(method: str) -> None:
    executor = RecordingExecutor(error=AssertionError("executor must not be called"))
    adapter = WpctlAdapter(executor=executor)

    with pytest.raises(NotImplementedError):
        getattr(adapter, method)(*(1, 2) if method == "set_profile" else ())

    assert executor.calls == []
