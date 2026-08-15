"""Unit tests for privacy-safe identifier redaction."""

from __future__ import annotations

from openbuds.infrastructure.redaction import (
    redact_addresses,
    redact_object_paths,
    sanitize_display,
)


def test_redact_addresses_supports_common_separators_and_boundaries() -> None:
    text = "00:11:22:33:44:55 00_11_22_33_44_55 00.11.22.33.44.55 00 11 22 33 44 55"

    redacted = redact_addresses(text)

    assert redacted == "<redacted> <redacted> <redacted> <redacted>"
    assert redact_addresses("x00:11:22:33:44:55") == "x00:11:22:33:44:55"
    assert redact_addresses("-00:11:22:33:44:55") == "-<redacted>"


def test_redact_object_paths() -> None:
    text = "/org/bluez/hci0/dev_00_11_22_33_44_55"

    assert redact_object_paths(text) == "<redacted>"


def test_sanitize_display_redacts_non_printable_text_and_limits_length() -> None:
    value = "prefix\x00 00:11:22:33:44:55 /org/bluez/hci0/dev_fake"

    sanitized = sanitize_display(value)

    assert "?" in sanitized
    assert "00:11:22:33:44:55" not in sanitized
    assert "/org/bluez/" not in sanitized
    assert sanitize_display("x" * 81) == "x" * 80


def test_sanitize_display_redacts_pipewire_node_ids_and_generic_paths() -> None:
    value = "bluez_output.42.1 bluez_input.7.2 /org/freedesktop/DBus"

    sanitized = sanitize_display(value)

    assert "bluez_output.42.1" not in sanitized
    assert "bluez_input.7.2" not in sanitized
    assert "/org/freedesktop/DBus" not in sanitized
    assert "<bluetooth-sink>" in sanitized
    assert "<bluetooth-source>" in sanitized


def test_sanitize_exception_preserves_class_and_safe_message() -> None:
    from openbuds.core.privacy import sanitize_exception

    try:
        raise RuntimeError("fallo en bluez_output.42.1 /org/bluez/hci0")
    except RuntimeError:
        sanitized = sanitize_exception()

    assert sanitized.startswith("RuntimeError: fallo en")
    assert "bluez_output.42.1" not in sanitized
    assert "/org/bluez/hci0" not in sanitized
