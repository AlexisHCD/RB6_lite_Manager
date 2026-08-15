"""Cargador y validador de perfiles de dispositivo (YAML -> DeviceProfile).

Estado: Etapa 0 — esqueleto bloqueado hasta aprobar la propuesta tipada y
obtener evidencia pasiva de la Etapa 1.
"""

from __future__ import annotations

from pathlib import Path

from openbuds.domain.interfaces.profile_repo import DeviceProfile

# Directorio de perfiles YAML fuente; los perfiles están fuera del paquete MVP.
PROFILES_DIR = Path(__file__).resolve().parent


def load_profile_from_yaml(path: Path) -> DeviceProfile:
    """Carga y valida un perfil desde un archivo YAML.

    Estado: Etapa 0 — sin implementación; bloqueado hasta aprobar la propuesta
    tipada y obtener evidencia pasiva de la Etapa 1.
    """
    raise NotImplementedError(
        "Device Profiles bloqueado hasta aprobar la propuesta tipada y obtener "
        "evidencia pasiva de la Etapa 1."
    )


def list_available_profiles() -> list[str]:
    """Devuelve los IDs de perfil disponibles en ``PROFILES_DIR``."""
    return sorted(p.stem for p in PROFILES_DIR.glob("*.yaml") if not p.name.startswith("_"))
