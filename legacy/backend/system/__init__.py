"""Paquete de detección del sistema."""

from backend.system.detector import (
    SystemReport,
    detect_system,
)

__all__ = ["SystemReport", "detect_system"]
