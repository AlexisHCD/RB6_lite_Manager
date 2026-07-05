"""Jerarquía de excepciones del dominio OpenBuds.

Todas las excepciones de negocio heredan de ``OpenBudsError``. Esto permite
que la capa de aplicación/presentación capture errores de forma uniforme y
que el logging los clasifique. Las excepciones concretas de librerías externas
(glib.Error, subprocess.CalledProcessError, etc.) se envuelven en estas.

Diseño: excepciones específicas anidadas bajo categorías, de forma que el
caller pueda atrapar a nivel granular o por categoría.
"""

from __future__ import annotations


class OpenBudsError(Exception):
    """Clase base de todas las excepciones de OpenBuds Manager."""


# ---------------------------------------------------------------------------
# Bluetooth / BlueZ
# ---------------------------------------------------------------------------
class BluetoothError(OpenBudsError):
    """Error de acceso al stack Bluetooth (BlueZ / D-Bus)."""


class AdapterNotFoundError(BluetoothError):
    """No se encontró ningún adaptador Bluetooth."""


class DeviceNotFoundError(BluetoothError):
    """El dispositivo solicitado no existe o no está disponible."""


# ---------------------------------------------------------------------------
# Subsistema de audio (PipeWire / WirePlumber)
# ---------------------------------------------------------------------------
class AudioSubsystemError(OpenBudsError):
    """Error de acceso al grafo de audio (PipeWire/WirePlumber)."""


class PipeWireUnavailableError(AudioSubsystemError):
    """El daemon PipeWire no está disponible o no responde."""


class WirePlumberUnavailableError(AudioSubsystemError):
    """El daemon WirePlumber no está disponible o no responde."""


class CodecDetectionError(AudioSubsystemError):
    """No se pudo determinar el códec activo de forma fiable."""


# ---------------------------------------------------------------------------
# Configuración y seguridad
# ---------------------------------------------------------------------------
class ConfigError(OpenBudsError):
    """Error de lectura/escritura de configuración."""


class BackupError(OpenBudsError):
    """No se pudo crear el backup previo requerido antes de un cambio.

    Por política de seguridad, si el backup falla, NO se aplica el cambio.
    """


class RollbackError(OpenBudsError):
    """No se pudo revertir un cambio tras un error de verificación."""


class UnsafeEnvironmentError(OpenBudsError):
    """El entorno no cumple los requisitos mínimos de seguridad/soporte."""


# ---------------------------------------------------------------------------
# Perfiles de dispositivo
# ---------------------------------------------------------------------------
class ProfileError(OpenBudsError):
    """Error de carga o validación de un perfil de dispositivo."""


class ProfileNotFoundError(ProfileError):
    """El perfil solicitado no existe."""


class ProfileValidationError(ProfileError):
    """El perfil existe pero su contenido es inválido."""
