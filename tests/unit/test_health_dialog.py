"""Tests for privacy-safe Health Check presentation formatting."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from openbuds.domain.enums import CheckSeverity, EvidenceKind, HealthStatus
from openbuds.domain.models import CheckResult, HealthReport
from openbuds.presentation.qt.health_dialog import format_health_error, format_health_report


def test_format_health_report_contains_fields_without_dynamic_identifiers() -> None:
    report = HealthReport(
        overall_status=HealthStatus.WARNING,
        checks=(
            CheckResult(
                check_id="bluez.service",
                label="Servicio Bluetooth",
                severity=CheckSeverity.WARNING,
                message="Revisar 00:11:22:33:44:55 en /org/bluez/hci0/dev_00_11_22_33_44_55",
                detail="detalle 00:11:22:33:44:55 /org/bluez/hci0",
                auto_fix_available=True,
                auto_fix_id="start.audio",
                evidence=EvidenceKind.OBSERVED,
            ),
        ),
        recommendations=("Revisar 00:11:22:33:44:55 /org/bluez/hci0",),
        generated_at="2026-08-13T12:00:00Z",
    )

    rendered = format_health_report(report)

    assert "Estado global: WARNING" in rendered
    assert "Severidad: WARNING" in rendered
    assert "ID: bluez.service" in rendered
    assert "Servicio Bluetooth" in rendered
    assert "Mensaje:" in rendered
    assert "Detalle:" in rendered
    assert "Evidencia: observado" in rendered
    assert "[fix: start.audio]" in rendered
    assert "Recomendaciones:" in rendered
    assert "00:11:22:33:44:55" not in rendered
    assert "/org/bluez/" not in rendered


def test_format_health_error_is_privacy_safe() -> None:
    rendered = format_health_error(
        "health failed 00:11:22:33:44:55 /org/bluez/hci0/dev_00_11_22_33_44_55"
    )

    assert "health failed" in rendered
    assert "00:11:22:33:44:55" not in rendered
    assert "/org/bluez/" not in rendered
