"""Ventana principal de OpenBuds Manager (PySide6).

Estado: Etapa 0 — scaffolding/placeholder legado con secciones provisionales.
Sin lógica de negocio; la ventana útil corresponde a la Etapa 3.
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

    Estado: Etapa 0 — sin implementación. Requiere un QApplication activo y
    un display; por eso no se instancia a nivel de módulo.
    """
    raise NotImplementedError("Implementación pendiente de la Etapa 3 (GUI MVP).")
