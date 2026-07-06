"""Persistencia de la configuración propia de la app (TOML en ~/.config/openbuds).

Implementa el almacenamiento en disco de ``AppConfig``. La lógica de
serialización (lectura/escritura TOML) vive en ``openbuds.core.config``; esta
clase es el adaptador que la presenta como un store con una ruta fija.
"""

from __future__ import annotations

from pathlib import Path

from openbuds.core.config import AppConfig, load_config, save_config


class AppConfigStore:
    """Carga y guarda la configuración de la app en disco.

    La ruta del archivo se fija en la construcción; típicamente
    ``~/.config/openbuds/config.toml`` (ver ``core.config.CONFIG_FILE``).
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> AppConfig:
        """Carga la configuración; devuelve defaults si el archivo no existe."""
        return load_config(self._path)

    def save(self, config: AppConfig) -> None:
        """Guarda la configuración en disco (creando el directorio si hace falta)."""
        save_config(config, self._path)
