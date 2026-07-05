"""Modelos de diagnóstico y Health Check."""

from __future__ import annotations

from dataclasses import dataclass, field

from openbuds.domain.enums import CheckSeverity, HealthStatus


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Resultado de una comprobación individual del Health Check.

    Atributos:
        check_id: Identificador estable de la comprobación
            (p. ej. "bluez.service", "pipewire.version", "adapter.powered").
        label: Etiqueta legible para mostrar en la UI.
        severity: Severidad del resultado (info/ok/warning/error).
        message: Mensaje descriptivo del hallazgo.
        detail: Detalle técnico opcional (salida de comando, versión, etc.).
        auto_fix_available: Si existe una reparación automática segura posible.
        auto_fix_id: Identificador de la reparación automática, si procede.
    """

    check_id: str
    label: str
    severity: CheckSeverity
    message: str
    detail: str = ""
    auto_fix_available: bool = False
    auto_fix_id: str = ""


@dataclass(frozen=True, slots=True)
class HealthReport:
    """Informe agregado de un Health Check completo del sistema.

    Atributos:
        overall_status: Estado global derivado de los resultados individuales.
        checks: Resultados individuales ordenados por categoría.
        recommendations: Recomendaciones legibles para el usuario.
        generated_at: Marca temporal de generación (UTC).
    """

    overall_status: HealthStatus
    checks: tuple[CheckResult, ...] = field(default_factory=tuple)
    recommendations: tuple[str, ...] = field(default_factory=tuple)
    generated_at: str = ""
