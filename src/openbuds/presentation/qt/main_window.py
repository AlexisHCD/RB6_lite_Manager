"""Ventana principal de OpenBuds Manager (PySide6).

Estado: Fase 1 — esqueleto con el sidebar de las 10 vistas requeridas por las
directrices (Dashboard, Dispositivo, Audio, Optimización, Health Check,
Diagnóstico, Benchmark, Logs, Configuración, Laboratorio Experimental).
Sin lógica de negocio; cada vista es un placeholder. Implementación en Fase 6.
"""

from __future__ import annotations

# Las vistas se importan de forma diferida dentro de la app Qt para que este
# módulo sea importable sin un display (p. ej. en tests headless).
VIEWS = (
    ("dashboard", "Dashboard"),
    ("device", "Dispositivo"),
    ("audio", "Audio"),
    ("optimization", "Optimización"),
    ("health_check", "Health Check"),
    ("diagnostic", "Diagnóstico"),
    ("benchmark", "Benchmark"),
    ("logs", "Logs"),
    ("settings", "Configuración"),
    ("lab", "Laboratorio Experimental"),
)


def build_main_window():
    """Construye y devuelve la QMainWindow de la app.

    Estado: Fase 1 — sin implementación. Requiere un QApplication activo y
    un display; por eso no se instancia a nivel de módulo.
    """
    raise NotImplementedError("Implementación diferada a Fase 6 (Interfaz gráfica).")
