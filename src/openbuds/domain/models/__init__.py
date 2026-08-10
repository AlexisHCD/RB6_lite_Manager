"""Modelos de datos del dominio.

Dataclasses inmutables que representan los conceptos del dominio Bluetooth/Audio.
Diseñadas para ser serializables y testeables sin depender del sistema.

Convención: las marcas de tiempo usan ``datetime`` consciente de zona horaria
(``tzinfo``). Los identificadores de objetos D-Bus se guardan como ``str``
(object path) pero la capa de dominio no asume formato concreto.
"""

from __future__ import annotations

from openbuds.domain.models.adapter import AdapterInfo
from openbuds.domain.models.battery import BatteryLevel
from openbuds.domain.models.benchmark import BenchmarkResult, BenchmarkSample
from openbuds.domain.models.codec import CodecInfo
from openbuds.domain.models.device import DeviceInfo
from openbuds.domain.models.diagnostic import CheckResult, HealthReport
from openbuds.domain.models.rssi import RSSIReading
from openbuds.domain.models.system import SystemInfo

__all__ = [
    "AdapterInfo",
    "BatteryLevel",
    "BenchmarkResult",
    "BenchmarkSample",
    "CheckResult",
    "CodecInfo",
    "DeviceInfo",
    "HealthReport",
    "RSSIReading",
    "SystemInfo",
]
