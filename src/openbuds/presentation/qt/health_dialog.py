"""Read-only Qt presentation for a Health Check report."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from openbuds.domain.enums import CheckSeverity, HealthStatus
from openbuds.domain.models import HealthReport
from openbuds.presentation.formatting import sanitize_display_field

_STATUS_LABELS = {
    HealthStatus.OK: "OK",
    HealthStatus.WARNING: "WARNING",
    HealthStatus.ERROR: "ERROR",
    HealthStatus.UNKNOWN: "UNKNOWN",
}
_SEVERITY_LABELS = {
    CheckSeverity.INFO: "INFO",
    CheckSeverity.OK: "OK",
    CheckSeverity.WARNING: "WARNING",
    CheckSeverity.ERROR: "ERROR",
}


def _safe(value: object) -> str:
    """Convert one dynamic report value to safe plain display text."""
    return sanitize_display_field(str(value))


def format_health_report(report: HealthReport) -> str:
    """Format every report field as selectable, privacy-safe plain text."""
    lines = [f"Estado global: {_safe(_STATUS_LABELS[report.overall_status])}"]
    if report.generated_at:
        lines.append(f"Generado: {_safe(report.generated_at)}")

    for index, check in enumerate(report.checks, start=1):
        if index > 1:
            lines.append("")
        lines.extend(
            (
                f"Check {index}",
                f"  Severidad: {_safe(_SEVERITY_LABELS[check.severity])}",
                f"  ID: {_safe(check.check_id)}",
                f"  Etiqueta: {_safe(check.label)}",
                f"  Mensaje: {_safe(check.message)}",
            )
        )
        if check.detail:
            lines.append(f"  Detalle: {_safe(check.detail)}")
        lines.append(f"  Evidencia: {_safe(check.evidence.value)}")
        if check.auto_fix_available and check.auto_fix_id:
            lines.append(f"  [fix: {_safe(check.auto_fix_id)}]")

    if report.recommendations:
        lines.extend(("", "Recomendaciones:"))
        lines.extend(f"- {_safe(recommendation)}" for recommendation in report.recommendations)

    return "\n".join(lines)


def format_health_error(message: str) -> str:
    """Format a failed Health Check error without exposing system identifiers."""
    safe_message = sanitize_display_field(message) or "No se pudo completar el Health Check."
    return f"No se pudo completar el Health Check.\n\nError: {safe_message}"


class HealthDialog(QDialog):
    """Display a Health Check while allowing the user to close it safely."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Diagnóstico")
        self.setMinimumSize(620, 480)
        self.setAccessibleName("Diálogo de Health Check")

        root_layout = QVBoxLayout(self)
        self.status_label = QLabel("Analizando...", self)
        self.status_label.setAccessibleName("Estado del Health Check")
        root_layout.addWidget(self.status_label)

        self.report_text = QPlainTextEdit(self)
        self.report_text.setReadOnly(True)
        self.report_text.setPlainText("Analizando...")
        self.report_text.setAccessibleName("Resultado del Health Check")
        self.report_text.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        root_layout.addWidget(self.report_text)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_button = QPushButton("Cerrar", self)
        close_button.setAccessibleName("Cerrar Health Check")
        close_button.clicked.connect(self.close)
        button_layout.addWidget(close_button)
        root_layout.addLayout(button_layout)

    def show_report(self, report: HealthReport) -> None:
        """Render a completed report and its global status."""
        status = _safe(_STATUS_LABELS[report.overall_status])
        self.status_label.setText(f"Estado global: {status}")
        self.report_text.setPlainText(format_health_report(report))

    def show_error(self, message: str) -> None:
        """Render a sanitized failure without offering any corrective action."""
        self.status_label.setText("Error")
        self.report_text.setPlainText(format_health_error(message))


__all__ = ["HealthDialog", "format_health_error", "format_health_report"]
