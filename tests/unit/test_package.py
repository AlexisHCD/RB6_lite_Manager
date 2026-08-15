"""Tests de integridad del paquete (importabilidad y metadatos básicos).

Estos tests garantizan que la estructura del proyecto es navegable y que los
contratos del dominio están accesibles desde los puntos de entrada esperados.
"""

from __future__ import annotations

import importlib
import tomllib
from pathlib import Path

import openbuds
from openbuds.domain import enums, models


def test_version_is_string() -> None:
    assert isinstance(openbuds.__version__, str)
    assert openbuds.__version__


def test_release_metadata_matches_mvp_version_and_status() -> None:
    pyproject = Path(__file__).parents[2] / "pyproject.toml"
    with pyproject.open("rb") as stream:
        project = tomllib.load(stream)["project"]

    assert project["version"] == "0.1.0"
    assert project["version"] == openbuds.__version__
    assert "Development Status :: 4 - Beta" in project["classifiers"]
    assert project["requires-python"] == ">=3.12,<3.13"
    assert "Programming Language :: Python :: 3.12" in project["classifiers"]
    assert "Programming Language :: Python :: 3.13" not in project["classifiers"]
    assert "Programming Language :: Python :: 3.14" not in project["classifiers"]


def test_profiles_are_not_runtime_packaging_dependencies() -> None:
    pyproject = Path(__file__).parents[2] / "pyproject.toml"
    with pyproject.open("rb") as stream:
        data = tomllib.load(stream)

    assert not any(str(dep).startswith("PyYAML") for dep in data["project"]["dependencies"])
    assert "package-data" not in data["tool"]["setuptools"]
    assert data["tool"]["setuptools"]["include-package-data"] is False
    assert data["tool"]["setuptools"]["packages"]["find"]["where"] == ["src"]


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
