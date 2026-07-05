"""Persistencia de la configuración propia de la app (TOML en ~/.config/openbuds).

Estado: Fase 1 — esqueleto. Implementación en Fase 2.
"""

from __future__ import annotations

from pathlib import Path

from openbuds.core.config import AppConfig


class AppConfigStore:
    """Carga y guarda la configuración de la app en disco.

    Estado: Fase 1 — sin implementación.
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> AppConfig:
        """Carga la configuración; devuelve defaults si el archivo no existe."""
        raise NotImplementedError("Fase 2 (Backend base).")

    def save(self, config: AppConfig) -> None:
        """Guarda la configuración en disco (creando el directorio si hace falta)."""
        raise NotImplementedError("Fase 2 (Backend base).")
