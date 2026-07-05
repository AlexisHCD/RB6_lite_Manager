"""Enumeraciones del dominio de OpenBuds Manager.

Estas enumeraciones describen los conceptos estables del dominio Bluetooth/Audio
de forma independiente a cualquier librería externa (BlueZ, PipeWire, WirePlumber).
La capa de infraestructura es responsable de traducir los valores concretos del
sistema (bytes de codec D-Bus, propiedades de nodos PipeWire) a estas
enumeraciones.

Referencias verificadas (ver docs/bluez/dbus-interfaces.md y docs/RESEARCH_LIMITS.md):
  - SBC = 0x00 y AAC = 0x02 son los únicos codec bytes A2DP canonizados en el
    estándar (A2DP v1.3). aptX/LDAC son endpoints de proveedor y NO están
    canonizados: se validan empíricamente en Fase 3/4.
"""

from __future__ import annotations

from enum import StrEnum, unique


@unique
class BluetoothProfile(StrEnum):
    """Perfiles Bluetooth Classic relevantes para auriculares."""

    A2DP = "a2dp"  # Advanced Audio Distribution Profile (audio de alta calidad)
    HFP = "hfp"  # Hands-Free Profile (voz bidireccional)
    HSP = "hsp"  # Headset Profile (voz bidireccional, predecesor de HFP)
    AVRCP = "avrcp"  # Audio/Video Remote Control Profile (controles multimedia)
    UNKNOWN = "unknown"


@unique
class CodecType(StrEnum):
    """Códecs de audio Bluetooth soportados o reconocibles.

    Nota: los valores se corresponden con los nombres canónicos usados por
    WirePlumber 0.4 (``bluez5.codecs``). El byte numérico A2DP se resuelve en
    la capa de infraestructura a partir de ``MediaTransport1.Codec``.
    """

    SBC = "sbc"  # 0x00 — obligatorio en A2DP
    SBC_XQ = "sbc_xq"  # variante SBC de alta calidad (WirePlumber)
    AAC = "aac"  # 0x02 (A2DP v1.3) — A VERIFICAR en dispositivo real
    APTX = "aptx"  # vendor — NO canonizado, validación empírica pendiente
    APTX_HD = "aptx_hd"  # vendor — NO canonizado, validación empírica pendiente
    APTX_LL = "aptx_ll"  # aptX Low Latency (duplex)
    LDAC = "ldac"  # vendor — NO canonizado, validación empírica pendiente
    FASTSTREAM = "faststream"
    MSBC = "msbc"  # códec SCO de voz (HFP)
    CVSD = "cvsd"  # códec SCO de voz (HFP/HSP, banda estrecha)
    UNKNOWN = "unknown"


@unique
class ConnectionState(StrEnum):
    """Estado de conexión de un dispositivo Bluetooth."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    UNKNOWN = "unknown"


@unique
class ProfileState(StrEnum):
    """Estado de un perfil Bluetooth activo (p. ej. A2DP Sink)."""

    INACTIVE = "inactive"
    AVAILABLE = "available"
    ACTIVE = "active"
    UNKNOWN = "unknown"


@unique
class DeviceIcon(StrEnum):
    """Categoría de dispositivo derivada de ``Device1.Icon`` de BlueZ."""

    AUDIO_CARD = "audio-card"
    INPUT_HEADSET = "input-headset"
    AUDIO_HEADSET = "audio-headset"
    AUDIO_INPUT_MICROPHONE = "audio-input-microphone"
    UNKNOWN = "unknown"


@unique
class HealthStatus(StrEnum):
    """Resultado global de un Health Check."""

    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    UNKNOWN = "unknown"


@unique
class CheckSeverity(StrEnum):
    """Severidad de un hallazgo individual del Health Check."""

    INFO = "info"
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


@unique
class AddressType(StrEnum):
    """Tipo de dirección Bluetooth (``Device1.AddressType``)."""

    PUBLIC = "public"
    RANDOM = "random"
    UNKNOWN = "unknown"
