"""Contrato provisional del repositorio de perfiles de dispositivo.

YAML es la dirección arquitectónica de ADR-0005, pero el contrato y el YAML
actuales son incompatibles. El contrato actual será revisado antes de habilitar
el loader, sujeto a una propuesta tipada aprobada y evidencia pasiva de la
Etapa 1.
"""

from __future__ import annotations

from openbuds.domain.models.device import DeviceInfo


class DeviceProfile:
    """Descripción estática provisional de un modelo soportado.

    El contrato se revisará antes de habilitar la carga desde YAML.

    Atributos:
        profile_id: Identificador estable (p. ej. "redmi_buds_6_lite").
        manufacturer: Fabricante.
        model: Modelo comercial.
        bluetooth_version: Versión Bluetooth soportada (p. ej. "5.3").
        supported_codecs: Códecs esperados (marcados como no verificados hasta
            validación empírica).
        bluetooth_profiles: Perfiles Bluetooth soportados (A2DP, HFP, ...).
        capabilities: Funciones disponibles conocidas.
        experimental_features: Funciones experimentales (no estables).
        known_limitations: Limitaciones conocidas del dispositivo.
    """

    profile_id: str
    manufacturer: str
    model: str
    bluetooth_version: str
    supported_codecs: tuple[str, ...]
    bluetooth_profiles: tuple[str, ...]
    capabilities: tuple[str, ...]
    experimental_features: tuple[str, ...]
    known_limitations: tuple[str, ...]


class IDeviceProfileRepository:
    """Carga y resolución de perfiles de dispositivo.

    Permite asociar un ``DeviceInfo`` detectado en el sistema con su perfil
    descriptivo (si existe soporte). El núcleo del programa nunca contiene
    lógica específica de un dispositivo; delega en los perfiles.
    """

    def list_profiles(self) -> list[str]:
        """Devuelve los identificadores de todos los perfiles disponibles."""
        raise NotImplementedError

    def load_profile(self, profile_id: str) -> DeviceProfile:
        """Carga un perfil por su identificador."""
        raise NotImplementedError

    def match_device(self, device: DeviceInfo) -> DeviceProfile | None:
        """Resuelve el perfil aplicable a un dispositivo detectado.

        La resolución se basa en heurísticas (vendor OUI de la MAC, nombre,
        icono, UUIDs). Devuelve ``None`` si no hay perfil conocido.
        """
        raise NotImplementedError
