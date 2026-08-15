"""Unit tests for the safe ``journalctl`` reader."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Any

import pytest

from openbuds.infrastructure.logs.journal_log_reader import JournalLogReader, sanitize_journal_line


@dataclass(frozen=True)
class FakeResult:
    """Minimal subprocess result fake."""

    returncode: int
    stdout: Any
    stderr: Any


@dataclass
class RecordingExecutor:
    """Executor fake that records commands without launching a process."""

    outcomes: list[FakeResult | BaseException]
    calls: list[tuple[list[str], dict[str, Any]]] = field(default_factory=list)

    def __call__(self, argv: list[str], **kwargs: Any) -> FakeResult:
        self.calls.append((argv, kwargs))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def test_success_sanitizes_output_and_uses_explicit_short_format() -> None:
    executor = RecordingExecutor(
        [
            FakeResult(
                0,
                "line 00:11:22:33:44:55 /org/bluez/hci0/dev_00_11_22_33_44_55\nsecond",
                "stderr secret",
            )
        ]
    )

    available, output, error = JournalLogReader(timeout_seconds=3.5, executor=executor).read(
        "bluez", 5
    )

    assert available is True
    assert output == "line <redacted> <redacted>\nsecond"
    assert error == ""
    assert executor.calls == [
        (
            ["journalctl", "-u", "bluetooth", "-n", "5", "--no-pager", "-o", "short"],
            {"capture_output": True, "text": True, "check": False, "timeout": 3.5},
        )
    ]
    assert executor.calls[0][0].count("-o") == 1


def test_nonzero_system_attempt_retries_user_journal_for_user_service() -> None:
    executor = RecordingExecutor(
        [
            FakeResult(1, "system secret", "permission denied"),
            FakeResult(0, "user line", ""),
        ]
    )

    result = JournalLogReader(executor=executor).read("wireplumber", 20)

    assert result == (True, "user line", "")
    assert len(executor.calls) == 2
    assert executor.calls[0][0] == [
        "journalctl",
        "-u",
        "wireplumber",
        "-n",
        "20",
        "--no-pager",
        "-o",
        "short",
    ]
    assert executor.calls[1][0] == [
        "journalctl",
        "--user",
        "-u",
        "wireplumber",
        "-n",
        "20",
        "--no-pager",
        "-o",
        "short",
    ]


def test_nonzero_bluez_attempt_is_not_retried_as_user() -> None:
    executor = RecordingExecutor([FakeResult(1, "secret", "")])

    result = JournalLogReader(executor=executor).read("bluez", 20)

    assert result == (False, "", "servicio no disponible o sin permisos")
    assert len(executor.calls) == 1


def test_sanitize_journal_line_redacts_short_metadata_and_dynamic_ids() -> None:
    line = (
        "ago 11 10:00:00 workstation wireplumber[1234]: "
        "sender=:1.42 ptr=0x7ff0abc12345 boot=0123456789abcdef0123456789abcdef"
    )

    sanitized = sanitize_journal_line(line)

    assert sanitized.startswith("ago 11 10:00:00 <host> wireplumber[PID]:")
    assert ":1.42" not in sanitized
    assert "[1234]" not in sanitized
    assert "0x7ff0abc12345" not in sanitized
    assert "0123456789abcdef0123456789abcdef" not in sanitized


def test_sanitize_journal_line_keeps_short_hex_values() -> None:
    sanitized = sanitize_journal_line("ago 11 10:00:00 host pipewire[7]: value=0x00")

    assert "value=0x00" in sanitized
    assert "<host> pipewire[PID]" in sanitized


def test_sanitize_journal_line_redacts_boot_id() -> None:
    sanitized = sanitize_journal_line("-- Boot 0123456789abcdef0123456789abcdef --")

    assert sanitized == "-- Boot <redacted> --"


def test_empty_system_unit_falls_back_to_user_journal_for_user_service() -> None:
    executor = RecordingExecutor(
        [
            FakeResult(0, "-- No entries --\n", ""),
            FakeResult(0, "ago 11 10:00:00 host wireplumber[123]: line\n", ""),
        ]
    )

    result = JournalLogReader(executor=executor).read("wireplumber", 20)

    assert result == (True, "ago 11 10:00:00 <host> wireplumber[PID]: line", "")
    assert len(executor.calls) == 2
    assert executor.calls[1][0][1] == "--user"


def test_nonzero_user_attempt_returns_safe_error() -> None:
    executor = RecordingExecutor([FakeResult(1, "secret", ""), FakeResult(2, "secret", "")])

    result = JournalLogReader(executor=executor).read("pipewire", 20)

    assert result == (False, "", "servicio no disponible o sin permisos")
    assert len(executor.calls) == 2


def test_file_not_found_is_reported_without_raw_output() -> None:
    executor = RecordingExecutor([FileNotFoundError("journalctl")])

    result = JournalLogReader(executor=executor).read("bluez", 20)

    assert result == (False, "", "journalctl no disponible")


def test_timeout_is_reported_without_exception_details() -> None:
    executor = RecordingExecutor([subprocess.TimeoutExpired(["journalctl"], 10)])

    result = JournalLogReader(executor=executor).read("pipewire", 20)

    assert result == (False, "", "journalctl excedió el tiempo límite")


@pytest.mark.parametrize("service", ["unknown", "", None])
def test_invalid_service_is_rejected(service: object) -> None:
    executor = RecordingExecutor([])

    with pytest.raises(ValueError):
        JournalLogReader(executor=executor).read(service, 20)  # type: ignore[arg-type]

    assert executor.calls == []


@pytest.mark.parametrize("lines", [0, 201, True, "20"])
def test_invalid_line_count_is_rejected(lines: object) -> None:
    executor = RecordingExecutor([])

    with pytest.raises(ValueError):
        JournalLogReader(executor=executor).read("bluez", lines)  # type: ignore[arg-type]

    assert executor.calls == []
