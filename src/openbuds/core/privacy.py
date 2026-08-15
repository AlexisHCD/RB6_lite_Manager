"""Shared privacy-safe formatting for user-visible and diagnostic text."""

from __future__ import annotations

import re
import sys
from types import TracebackType

type ExceptionInfo = tuple[type[BaseException] | None, BaseException | None, TracebackType | None]

_REDACT_OBJECT_PATH = re.compile(
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+(?![A-Za-z0-9_])"
)
_REDACT_ADDRESS = re.compile(
    r"(?<![A-Za-z0-9])[0-9A-Fa-f]{2}(?:[:_. \-]?[0-9A-Fa-f]{2}){5}(?![A-Za-z0-9])"
)
_REDACT_PIPEWIRE_NODE = re.compile(r"(?<![A-Za-z0-9_-])bluez_(output|input)\.[^\s\]\[(),;]+")
_REDACT_DBUS_UNIQUE = re.compile(r"(?<![A-Za-z0-9_]):[0-9]+(?:\.[0-9]+)*\b")
_REDACT_HEX_ID = re.compile(
    r"(?<![A-Za-z0-9])(?:0x[0-9A-Fa-f]{4,}|[0-9A-Fa-f]{16,})(?![A-Za-z0-9])"
)


def redact_object_paths(text: str) -> str:
    """Redact D-Bus and similar object paths."""
    return _REDACT_OBJECT_PATH.sub("<redacted>", text)


def redact_addresses(text: str) -> str:
    """Redact Bluetooth addresses in common textual representations."""
    return _REDACT_ADDRESS.sub("<redacted>", text)


def redact_pipewire_nodes(text: str) -> str:
    """Replace dynamic Bluetooth PipeWire node names with stable labels."""
    return _REDACT_PIPEWIRE_NODE.sub(
        lambda match: "<bluetooth-sink>" if match.group(1) == "output" else "<bluetooth-source>",
        text,
    )


def redact_dynamic_ids(text: str) -> str:
    """Redact D-Bus unique names, pointers, and long hexadecimal IDs."""
    sanitized = _REDACT_DBUS_UNIQUE.sub("<redacted>", text)
    return _REDACT_HEX_ID.sub("<redacted>", sanitized)


def sanitize_text(text: str, limit: int = 80) -> str:
    """Redact dynamic identifiers, normalize control characters, and bound text."""
    sanitized = redact_pipewire_nodes(text)
    sanitized = redact_object_paths(sanitized)
    sanitized = redact_addresses(sanitized)
    sanitized = redact_dynamic_ids(sanitized)
    sanitized = "".join(character if character.isprintable() else "?" for character in sanitized)
    return sanitized[:limit]


def sanitize_exception(exc_info: ExceptionInfo | None = None, limit: int = 300) -> str:
    """Keep an exception class and safe message without exposing its traceback."""
    info = exc_info or sys.exc_info()
    if not info:
        return ""
    exception_type, exception, _traceback = info
    if exception_type is None or exception is None:
        return ""
    return sanitize_text(f"{exception_type.__name__}: {exception}", limit=limit)
