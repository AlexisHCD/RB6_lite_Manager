"""Unit tests for the safe ``pw-cli`` runner."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Any

import pytest

from openbuds.core.errors import PipeWireUnavailableError
from openbuds.infrastructure.pipewire.pw_cli_runner import PwCliRunner


@dataclass(frozen=True)
class FakeResult:
    """Minimal subprocess result fake."""

    returncode: int
    stdout: Any
    stderr: Any


@dataclass
class RecordingExecutor:
    """Executor fake that records arguments without launching a process."""

    result: FakeResult | None = None
    error: BaseException | None = None
    calls: list[tuple[list[str], dict[str, Any]]] = field(default_factory=list)

    def __call__(self, argv: list[str], **kwargs: Any) -> FakeResult:
        self.calls.append((argv, kwargs))
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def test_enum_params_uses_exact_command_and_timeout() -> None:
    executor = RecordingExecutor(FakeResult(0, "profiles", ""))

    assert PwCliRunner(timeout_seconds=3.5, executor=executor).enum_params(42) == "profiles"

    assert executor.calls == [
        (
            ["pw-cli", "enum-params", "42", "EnumProfile"],
            {"capture_output": True, "text": True, "check": False, "timeout": 3.5},
        )
    ]
    assert "shell" not in executor.calls[0][1]


@pytest.mark.parametrize("device_id", [True, -1, None, "42"])
def test_enum_params_rejects_invalid_device_id(device_id: object) -> None:
    executor = RecordingExecutor(error=AssertionError("executor must not be called"))

    with pytest.raises(ValueError):
        PwCliRunner(executor=executor).enum_params(device_id)  # type: ignore[arg-type]

    assert executor.calls == []


@pytest.mark.parametrize(
    "error",
    [OSError("missing"), subprocess.TimeoutExpired(["pw-cli"], 5)],
)
def test_executor_errors_are_wrapped_without_sensitive_details(error: BaseException) -> None:
    executor = RecordingExecutor(error=error)

    with pytest.raises(PipeWireUnavailableError) as raised:
        PwCliRunner(binary="/secret/pw-cli", executor=executor).enum_params(42)

    assert raised.value.__cause__ is error
    assert "/secret/pw-cli" not in str(raised.value)


def test_nonzero_result_is_unavailable_without_output() -> None:
    executor = RecordingExecutor(FakeResult(1, "stdout secret", "stderr secret"))

    with pytest.raises(PipeWireUnavailableError) as raised:
        PwCliRunner(executor=executor).enum_params(42)

    assert "secret" not in str(raised.value)


def test_success_requires_text_stdout() -> None:
    executor = RecordingExecutor(FakeResult(0, b"bytes", ""))

    with pytest.raises(PipeWireUnavailableError):
        PwCliRunner(executor=executor).enum_params(42)
