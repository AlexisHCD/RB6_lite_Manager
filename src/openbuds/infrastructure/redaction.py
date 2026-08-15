"""Privacy-safe redaction helpers for infrastructure output."""

from __future__ import annotations

from openbuds.core.privacy import (
    redact_addresses as _redact_addresses,
)
from openbuds.core.privacy import (
    redact_object_paths as _redact_object_paths,
)
from openbuds.core.privacy import (
    sanitize_text,
)


def redact_object_paths(text: str) -> str:
    """Redact D-Bus object paths from text."""
    return _redact_object_paths(text)


def redact_addresses(text: str) -> str:
    """Redact Bluetooth addresses from text."""
    return _redact_addresses(text)


def sanitize_display(text: str, limit: int = 80) -> str:
    """Redact identifiers, replace non-printable characters, and limit text."""
    return sanitize_text(text, limit=limit)
