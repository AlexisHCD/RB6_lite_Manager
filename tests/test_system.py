"""Pruebas para el módulo de detección del sistema."""

from __future__ import annotations

from backend.system.detector import (
    DistroInfo,
    KernelInfo,
    SystemReport,
    detect_system,
    _detect_distro,
    _detect_kernel,
)


class TestDistroDetection:
    """Pruebas de detección de distribución."""

    def test_distro_returns_distro_info(self) -> None:
        result = _detect_distro()
        assert isinstance(result, DistroInfo)

    def test_distro_has_name(self) -> None:
        result = _detect_distro()
        assert result.name != ""

    def test_distro_has_id(self) -> None:
        result = _detect_distro()
        assert result.id != ""


class TestKernelDetection:
    """Pruebas de detección del kernel."""

    def test_kernel_returns_kernel_info(self) -> None:
        result = _detect_kernel()
        assert isinstance(result, KernelInfo)

    def test_kernel_has_release(self) -> None:
        result = _detect_kernel()
        assert result.release != ""

    def test_kernel_has_machine(self) -> None:
        result = _detect_kernel()
        assert result.machine != ""


class TestSystemReport:
    """Pruebas del reporte completo del sistema."""

    def test_detect_system_returns_report(self) -> None:
        report = detect_system()
        assert isinstance(report, SystemReport)

    def test_report_has_distro(self) -> None:
        report = detect_system()
        assert isinstance(report.distro, DistroInfo)

    def test_report_has_kernel(self) -> None:
        report = detect_system()
        assert isinstance(report.kernel, KernelInfo)

    def test_report_has_python_version(self) -> None:
        report = detect_system()
        assert report.python_version != ""
