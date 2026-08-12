"""Opt-in read-only integration test for runtime profile discovery."""

from __future__ import annotations

import os

import pytest

from openbuds.infrastructure.pipewire.pipewire_control_repository import (
    PipeWireControlRepository,
)


@pytest.mark.integration
def test_real_control_repository_lists_profiles_without_mutating_audio() -> None:
    """Discover profiles for a fictitious address without changing any profile."""
    if os.environ.get("OPENBUDS_RUN_INTEGRATION") != "1":
        pytest.skip("integración PipeWire desactivada; usa OPENBUDS_RUN_INTEGRATION=1")

    profiles = PipeWireControlRepository().list_profiles("00:11:22:33:44:55")

    assert isinstance(profiles, tuple)
    assert all(isinstance(profile, str) for profile in profiles)
