"""Contratos (interfaces) del dominio.

Estas clases abstractas definen los límites del dominio. La capa de
infraestructura (``openbuds.infrastructure``) las implementa usando librerías
concretas (PyGObject/Gio para BlueZ D-Bus, subprocess para PipeWire/WirePlumber).
La capa de aplicación (``openbuds.application``) depende solo de estas
interfaces, nunca de implementaciones concretas.

Esto cumple el principio de inversión de dependencias (SOLID): las capas
internas no conocen los detalles técnicos de las externas.
"""

from __future__ import annotations

from openbuds.domain.interfaces.audio_control_repo import IAudioControlRepository
from openbuds.domain.interfaces.audio_repo import IAudioRepository
from openbuds.domain.interfaces.bluetooth_repo import IBluetoothRepository
from openbuds.domain.interfaces.config_repo import IConfigRepository
from openbuds.domain.interfaces.diagnostics_repo import IDiagnosticsRepository
from openbuds.domain.interfaces.profile_repo import IDeviceProfileRepository
from openbuds.domain.interfaces.user_service_controller import IUserServiceController

__all__ = [
    "IAudioRepository",
    "IAudioControlRepository",
    "IBluetoothRepository",
    "IConfigRepository",
    "IDiagnosticsRepository",
    "IDeviceProfileRepository",
    "IUserServiceController",
]
