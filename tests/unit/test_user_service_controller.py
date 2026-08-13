"""Unit tests for the safe user-service controller."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Any

import pytest

from openbuds.core.errors import ServiceError
from openbuds.infrastructure.system.user_service_controller import UserServiceController


@dataclass(frozen=True)
class FakeResult:
    """Minimal subprocess result fake."""

    returncode: int
    stdout: Any
    stderr: Any


@dataclass
class RecordingExecutor:
    """Executor fake that records commands without launching a process."""

    result: FakeResult | None = None
    error: BaseException | None = None
    calls: list[tuple[list[str], dict[str, Any]]] = field(default_factory=list)

    def __call__(self, argv: list[str], **kwargs: Any) -> FakeResult:
        self.calls.append((argv, kwargs))
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def test_start_uses_user_scope_and_exact_units() -> None:
    executor = RecordingExecutor(FakeResult(0, "", ""))

    UserServiceController(timeout_seconds=3.5, executor=executor).start(("pipewire", "wireplumber"))

    assert executor.calls == [
        (
            ["systemctl", "--user", "start", "pipewire", "wireplumber"],
            {"capture_output": True, "text": True, "check": False, "timeout": 3.5},
        )
    ]
    assert "sudo" not in executor.calls[0][0]


def test_start_nonzero_result_is_safe_and_redacts_stderr() -> None:
    executor = RecordingExecutor(FakeResult(1, "", "failed for 00:11:22:33:44:55"))

    with pytest.raises(ServiceError) as raised:
        UserServiceController(executor=executor).start(("pipewire",))

    assert "no se pudieron iniciar las unidades de usuario" in str(raised.value)
    assert "código 1" in str(raised.value)
    assert "00:11:22:33:44:55" not in str(raised.value)


@pytest.mark.parametrize(
    "error",
    [
        subprocess.TimeoutExpired(["systemctl"], 10),
        OSError("systemctl missing"),
    ],
)
def test_start_executor_errors_are_wrapped(error: BaseException) -> None:
    executor = RecordingExecutor(error=error)

    with pytest.raises(ServiceError) as raised:
        UserServiceController(executor=executor).start(("pipewire",))

    if isinstance(error, OSError):
        assert str(raised.value) == "systemctl no disponible"


@pytest.mark.parametrize("units", [(), ("",), ("pipewire\x00",)])
def test_start_rejects_invalid_units(units: tuple[str, ...]) -> None:
    executor = RecordingExecutor(error=AssertionError("executor must not be called"))

    with pytest.raises(ValueError):
        UserServiceController(executor=executor).start(units)

    assert executor.calls == []


def test_is_active_returns_true_for_success_and_false_for_failure() -> None:
    active_executor = RecordingExecutor(FakeResult(0, "active\n", ""))
    inactive_executor = RecordingExecutor(FakeResult(3, "inactive\n", ""))

    assert UserServiceController(executor=active_executor).is_active("pipewire") is True
    assert UserServiceController(executor=inactive_executor).is_active("pipewire") is False


def test_is_active_returns_false_when_executor_is_unavailable() -> None:
    executor = RecordingExecutor(error=OSError("systemctl missing"))

    assert UserServiceController(executor=executor).is_active("pipewire") is False
