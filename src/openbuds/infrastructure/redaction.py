"""Privacy-safe redaction helpers for infrastructure output."""

from __future__ import annotations

import re

_REDACT_OBJECT_PATH = re.compile(r"/org/bluez/[^\s]+")
_REDACT_ADDRESS = re.compile(
    r"(?<![A-Za-z0-9])[0-9A-Fa-f]{2}(?:[:_. ]?[0-9A-Fa-f]{2}){5}(?![A-Za-z0-9])"
)


def redact_object_paths(text: str) -> str:
    """Redact BlueZ object paths from text."""
    return _REDACT_OBJECT_PATH.sub("<redacted>", text)


def redact_addresses(text: str) -> str:
    """Redact Bluetooth addresses from text."""
    return _REDACT_ADDRESS.sub("<redacted>", text)


def sanitize_display(text: str, limit: int = 80) -> str:
    """Redact identifiers, replace non-printable characters, and limit text."""
    sanitized = redact_object_paths(text)
    sanitized = redact_addresses(sanitized)
    sanitized = "".join(character if character.isprintable() else "?" for character in sanitized)
    return sanitized[:limit]
