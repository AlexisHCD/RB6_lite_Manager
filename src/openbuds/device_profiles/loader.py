"""Cargador y validador de perfiles de dispositivo (YAML -> DeviceProfile).

Estado: Fase 1 — esqueleto. Implementación en Fase 7.
"""

from __future__ import annotations

from pathlib import Path

from openbuds.domain.interfaces.profile_repo import DeviceProfile

# Directorio donde residen los perfiles YAML empaquetados con la app.
PROFILES_DIR = Path(__file__).resolve().parent


def load_profile_from_yaml(path: Path) -> DeviceProfile:
    """Carga y valida un perfil desde un archivo YAML.

    Estado: Fase 1 — sin implementación.
    """
    raise NotImplementedError("Fase 7 (Device Profiles).")


def list_available_profiles() -> list[str]:
    """Devuelve los IDs de perfil disponibles en ``PROFILES_DIR``."""
    return sorted(p.stem for p in PROFILES_DIR.glob("*.yaml") if not p.name.startswith("_"))
