"""Tests de integridad del paquete (importabilidad y metadatos básicos).

Estos tests garantizan que la estructura del proyecto es navegable y que los
contratos del dominio están accesibles desde los puntos de entrada esperados.
"""

from __future__ import annotations

import importlib

import openbuds
from openbuds.domain import enums, models


def test_version_is_string() -> None:
    assert isinstance(openbuds.__version__, str)
    assert openbuds.__version__


def test_domain_models_importable_from_package() -> None:
    # Los modelos clave deben ser importables desde openbuds.domain.models.
    expected = {
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
    }
    available = set(models.__all__)
    assert expected.issubset(available), f"Faltan modelos: {expected - available}"


def test_interfaces_importable() -> None:
    # Los contratos deben ser importables desde openbuds.domain.interfaces.
    mod = importlib.import_module("openbuds.domain.interfaces")
    expected = {
        "IAudioRepository",
        "IBluetoothRepository",
        "IConfigRepository",
        "IDiagnosticsRepository",
        "IDeviceProfileRepository",
    }
    available = set(mod.__all__)
    assert expected.issubset(available)


def test_enums_module_has_expected_members() -> None:
    expected = {
        "BluetoothProfile",
        "CodecType",
        "ConnectionState",
        "ProfileState",
        "DeviceIcon",
        "HealthStatus",
        "CheckSeverity",
        "AddressType",
    }
    available = {name for name in dir(enums) if not name.startswith("_")}
    assert expected.issubset(available)
