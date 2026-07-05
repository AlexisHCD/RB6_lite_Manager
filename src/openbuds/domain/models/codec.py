"""Modelo de información de códec (``MediaTransport1`` / WirePlumber)."""

from __future__ import annotations

from dataclasses import dataclass

from openbuds.domain.enums import BluetoothProfile, CodecType


@dataclass(frozen=True, slots=True)
class CodecInfo:
    """Información sobre el códec de audio activo para un dispositivo.

    Combina datos de BlueZ (``MediaTransport1.Codec`` como byte) y/o PipeWire
    (propiedad de nodo ``device.profile`` / ``bluez5.codec``).

    Atributos:
        codec: Tipo de códec identificado (ver ``CodecType``).
        profile: Perfil Bluetooth en uso (A2DP / HFP / HSP).
        a2dp_codec_byte: Byte crudo ``MediaTransport1.Codec`` (None si N/A).
            Útil para depuración y para codecs vendor sin canonizar.
        verified: Si la identificación del códec está verificada empíricamente.
            Los codecs vendor (aptX/LDAC) se marcan ``False`` hasta validación
            en dispositivo real (ver docs/RESEARCH_LIMITS.md).
        configuration_hex: Configuración específica del códec (blob
            ``MediaTransport1.Configuration``) en hex, si está disponible.
    """

    codec: CodecType
    profile: BluetoothProfile
    a2dp_codec_byte: int | None = None
    verified: bool = True
    configuration_hex: str = ""
