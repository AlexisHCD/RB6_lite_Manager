"""Perfil declarativo y conservador para Redmi Buds 6 Lite."""

from __future__ import annotations

from dataclasses import dataclass

from ob_logging.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class RedmiBuds6LiteProfile:
    """Capacidades conocidas sin asumir datos propietarios del dispositivo."""

    name_pattern: tuple[str, ...] = ("Redmi Buds 6 Lite", "Redmi Buds 6")
    supported_codecs: tuple[str, ...] = ("SBC", "AAC", "LDAC")
    default_profile: str = "A2DP"


def match_device(device_name: str) -> bool:
    """Reconoce variantes del nombre comercial de forma insensible a mayúsculas."""
    return "redmi buds 6" in device_name.casefold()
