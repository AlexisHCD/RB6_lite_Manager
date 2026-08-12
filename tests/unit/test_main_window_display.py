"""Unit tests for the Qt display availability guards."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ctypes

import pytest

pytest.importorskip("PySide6")

from openbuds.presentation.qt.main_window import (
    _display_is_available,
    _xcb_cursor_available,
)


def test_xcb_cursor_available_when_library_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ctypes, "CDLL", lambda _name: object())

    assert _xcb_cursor_available() is True


def test_xcb_cursor_available_false_when_library_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_oserror(_name: str) -> object:
        raise OSError("library not found")

    monkeypatch.setattr(ctypes, "CDLL", raise_oserror)

    assert _xcb_cursor_available() is False


def test_display_available_with_offscreen_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)

    assert _display_is_available() is True


def test_display_available_with_wayland(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")

    assert _display_is_available() is True


def test_display_available_with_x11_and_cursor_library(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setattr(ctypes, "CDLL", lambda _name: object())

    assert _display_is_available() is True


def test_display_unavailable_with_x11_and_missing_cursor_library(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_oserror(_name: str) -> object:
        raise OSError("library not found")

    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setattr(ctypes, "CDLL", raise_oserror)

    assert _display_is_available() is False


def test_display_unavailable_without_any_display(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)

    assert _display_is_available() is False
