"""Pruebas unitarias del runner seguro de ``pw-dump``."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Any

import pytest

from openbuds.core.errors import AudioSubsystemError, PipeWireUnavailableError
from openbuds.infrastructure.pipewire.pw_dump_runner import PwDumpRunner


@dataclass(frozen=True)
class FakePwDumpResult:
    """Resultado mínimo compatible con el protocolo del runner."""

    returncode: int
    stdout: Any
    stderr: Any


@dataclass
class RecordingExecutor:
    """Executor fake que registra cada invocación sin ejecutar procesos."""

    result: FakePwDumpResult | None = None
    error: BaseException | None = None
    calls: list[tuple[list[str], dict[str, Any]]] = field(default_factory=list)

    def __call__(self, argv: list[str], **kwargs: Any) -> FakePwDumpResult:
        self.calls.append((argv, kwargs))
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def test_dump_uses_exact_argv_and_subprocess_kwargs() -> None:
    executor = RecordingExecutor(FakePwDumpResult(0, "payload", ""))

    assert PwDumpRunner(binary="pw-dump", timeout_seconds=3.5, executor=executor).dump() == (
        "payload"
    )

    assert executor.calls == [
        (
            ["pw-dump", "--no-colors"],
            {
                "capture_output": True,
                "text": True,
                "check": False,
                "timeout": 3.5,
            },
        )
    ]
    assert "shell" not in executor.calls[0][1]
    assert "env" not in executor.calls[0][1]
    assert "cwd" not in executor.calls[0][1]


@pytest.mark.parametrize("stdout", ["áé ñ 🚀\n  exact  ", ""])
def test_dump_returns_stdout_exactly(stdout: str) -> None:
    executor = RecordingExecutor(FakePwDumpResult(0, stdout, "ignored"))

    assert PwDumpRunner(executor=executor).dump() == stdout


def test_repeated_dump_calls_invoke_executor_again_without_cache() -> None:
    executor = RecordingExecutor(FakePwDumpResult(0, "fresh", ""))
    runner = PwDumpRunner(executor=executor)

    assert runner.dump() == "fresh"
    assert runner.dump() == "fresh"
    assert len(executor.calls) == 2
    assert executor.calls[0] == executor.calls[1]
    assert executor.calls[0] is not executor.calls[1]


def test_binary_path_with_spaces_is_one_argv_element() -> None:
    binary = "/opt/my tools/pw-dump"
    executor = RecordingExecutor(FakePwDumpResult(0, "", ""))

    PwDumpRunner(binary=binary, executor=executor).dump()

    assert executor.calls[0][0] == [binary, "--no-colors"]


@pytest.mark.parametrize("binary", ["", "pw-dump\x00x", None, 123])
def test_invalid_binary_is_rejected_before_executor(binary: object) -> None:
    executor = RecordingExecutor(error=AssertionError("executor must not be called"))

    with pytest.raises(ValueError):
        PwDumpRunner(binary=binary, executor=executor)  # type: ignore[arg-type]

    assert executor.calls == []


@pytest.mark.parametrize("timeout", [0, -1, True, "5", None, float("nan"), float("inf")])
def test_invalid_timeout_is_rejected_before_executor(timeout: object) -> None:
    executor = RecordingExecutor(error=AssertionError("executor must not be called"))

    with pytest.raises(ValueError):
        PwDumpRunner(timeout_seconds=timeout, executor=executor)  # type: ignore[arg-type]

    assert executor.calls == []


@pytest.mark.parametrize("timeout", [3, 3.5])
def test_valid_int_and_float_timeouts_are_accepted(timeout: int | float) -> None:
    PwDumpRunner(timeout_seconds=timeout, executor=RecordingExecutor())


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError("missing"),
        PermissionError("denied"),
        OSError("os failure"),
        subprocess.TimeoutExpired(["pw-dump"], 5),
    ],
)
def test_executor_failures_are_wrapped_with_the_original_cause(error: BaseException) -> None:
    executor = RecordingExecutor(error=error)
    runner = PwDumpRunner(binary="/sensitive/path/pw-dump", executor=executor)

    with pytest.raises(PipeWireUnavailableError) as raised:
        runner.dump()

    assert raised.value.__cause__ is error
    assert "/sensitive/path/pw-dump" not in str(raised.value)


def test_unexpected_executor_error_is_propagated_unchanged() -> None:
    error = RuntimeError("fake programming failure")
    runner = PwDumpRunner(executor=RecordingExecutor(error=error))

    with pytest.raises(RuntimeError) as raised:
        runner.dump()

    assert raised.value is error


def test_nonzero_result_is_wrapped_without_output_or_binary_path() -> None:
    binary = "/secret/path/pw-dump"
    stdout = "stdout secret"
    stderr = "SECRETO_MAC:aa:bb:cc:dd:ee:ff"
    runner = PwDumpRunner(
        binary=binary,
        executor=RecordingExecutor(FakePwDumpResult(7, stdout, stderr)),
    )

    with pytest.raises(PipeWireUnavailableError) as raised:
        runner.dump()

    message = str(raised.value)
    assert stdout not in message
    assert stderr not in message
    assert binary not in message


@pytest.mark.parametrize("stdout", [b"bytes", 123, object()])
def test_success_with_non_string_stdout_is_unavailable(stdout: object) -> None:
    runner = PwDumpRunner(executor=RecordingExecutor(FakePwDumpResult(0, stdout, "")))

    with pytest.raises(PipeWireUnavailableError):
        runner.dump()


def test_success_payload_with_mac_is_returned_and_not_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    payload = '{"node.name":"bluez_output.AA:BB:CC:DD:EE:FF"}'
    runner = PwDumpRunner(executor=RecordingExecutor(FakePwDumpResult(0, payload, "")))

    assert runner.dump() == payload
    assert caplog.records == []
    assert payload not in caplog.text


def test_unavailable_error_is_exact_subclass_of_audio_subsystem_error() -> None:
    runner = PwDumpRunner(executor=RecordingExecutor(FakePwDumpResult(1, "", "")))

    with pytest.raises(PipeWireUnavailableError) as raised:
        runner.dump()

    assert type(raised.value) is PipeWireUnavailableError
    assert isinstance(raised.value, AudioSubsystemError)
