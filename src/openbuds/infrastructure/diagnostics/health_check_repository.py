"""Read-only Health Check repository for the local Linux audio stack."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from openbuds.core.errors import BluetoothError, WirePlumberUnavailableError
from openbuds.domain.enums import (
    BluetoothProfile,
    CheckSeverity,
    CodecType,
    EvidenceKind,
    HealthStatus,
)
from openbuds.domain.interfaces import (
    IAudioRepository,
    IBluetoothRepository,
    IDiagnosticsRepository,
)
from openbuds.domain.models import (
    BenchmarkResult,
    CheckResult,
    CodecInfo,
    DeviceInfo,
    HealthReport,
    SystemInfo,
)
from openbuds.infrastructure.system import environment_detector

_REDACT_OBJECT_PATH = re.compile(r"/org/bluez/[^\s]+")
_REDACT_ADDRESS = re.compile(
    r"(?<![A-Za-z0-9])[0-9A-Fa-f]{2}(?:[:_. ]?[0-9A-Fa-f]{2}){5}(?![A-Za-z0-9])"
)

_CHECK_ORDER = (
    "system.os",
    "system.bluez",
    "system.pipewire",
    "system.wireplumber",
    "system.dbus",
    "runtime.gio",
    "hardware.adapter",
    "device.paired",
    "device.connected",
    "audio.profile",
    "audio.codec",
    "audio.sink_default",
    "audio.mic",
    "battery.aggregate",
)


@dataclass(frozen=True, slots=True)
class _CheckOutcome:
    """Internal result that records whether a check was evaluated."""

    result: CheckResult
    evaluated: bool = True


class HealthCheckRepository(IDiagnosticsRepository):
    """Collect a stable, read-only Health Check snapshot."""

    def __init__(
        self,
        bluetooth: IBluetoothRepository,
        audio: IAudioRepository,
        detect: Callable[[], SystemInfo] | None = None,
        runtime_ready: Callable[[], bool] | None = None,
    ) -> None:
        self._bluetooth = bluetooth
        self._audio = audio
        self._detect = detect if detect is not None else environment_detector.detect
        self._runtime_ready = (
            runtime_ready if runtime_ready is not None else environment_detector.is_runtime_ready
        )

    def detect_system(self) -> SystemInfo:
        """Return the detected system information."""
        return self._detect()

    def run_health_check(self) -> HealthReport:
        """Evaluate all checks without allowing one failure to abort the report."""
        checks: list[CheckResult] = []
        recommendations: list[str] = []
        evaluated_any = False

        def record(outcome: _CheckOutcome) -> CheckResult:
            nonlocal evaluated_any
            checks.append(outcome.result)
            evaluated_any = evaluated_any or outcome.evaluated
            return outcome.result

        def add(
            check_id: str,
            label: str,
            callback: Callable[[], CheckResult | _CheckOutcome],
        ) -> CheckResult:
            return record(self._run_isolated(check_id, label, callback))

        try:
            system_info: SystemInfo | None = self.detect_system()
        except Exception:
            system_info = None

        system_labels = {
            "system.os": "Sistema operativo",
            "system.bluez": "BlueZ",
            "system.pipewire": "PipeWire",
            "system.wireplumber": "WirePlumber",
            "system.dbus": "Bus del sistema",
            "hardware.adapter": "Adaptador Bluetooth",
        }
        if system_info is None:
            for check_id in (
                "system.os",
                "system.bluez",
                "system.pipewire",
                "system.wireplumber",
                "system.dbus",
            ):
                record(
                    _CheckOutcome(
                        self._result(
                            check_id,
                            system_labels[check_id],
                            CheckSeverity.ERROR,
                            "no se pudo detectar",
                            evidence=EvidenceKind.NOT_AVAILABLE,
                        ),
                        evaluated=False,
                    )
                )
        else:
            add(
                "system.os",
                system_labels["system.os"],
                lambda: self._check_os(system_info),
            )
            add(
                "system.bluez",
                system_labels["system.bluez"],
                lambda: self._check_version(
                    "system.bluez",
                    system_labels["system.bluez"],
                    "BlueZ",
                    system_info.bluez_version,
                ),
            )
            add(
                "system.pipewire",
                system_labels["system.pipewire"],
                lambda: self._check_version(
                    "system.pipewire",
                    system_labels["system.pipewire"],
                    "PipeWire",
                    system_info.pipewire_version,
                ),
            )
            add(
                "system.wireplumber",
                system_labels["system.wireplumber"],
                lambda: self._check_wireplumber(system_info),
            )
            add(
                "system.dbus",
                system_labels["system.dbus"],
                lambda: self._check_system_bus(system_info),
            )

        runtime_ready = False

        def check_runtime() -> CheckResult | _CheckOutcome:
            nonlocal runtime_ready
            try:
                runtime_ready = self._runtime_ready()
            except Exception:
                runtime_ready = False
                return _CheckOutcome(
                    self._result(
                        "runtime.gio",
                        "Runtime PyGObject/Gio",
                        CheckSeverity.ERROR,
                        "instala PyGObject/Gio o recrea el venv con "
                        "/usr/bin/python3 (make check-runtime)",
                        evidence=EvidenceKind.NOT_AVAILABLE,
                    ),
                    evaluated=False,
                )
            if runtime_ready:
                return self._result(
                    "runtime.gio",
                    "Runtime PyGObject/Gio",
                    CheckSeverity.OK,
                    "runtime listo (base /usr)",
                )
            return self._result(
                "runtime.gio",
                "Runtime PyGObject/Gio",
                CheckSeverity.ERROR,
                "instala PyGObject/Gio o recrea el venv con /usr/bin/python3 (make check-runtime)",
                evidence=EvidenceKind.NOT_AVAILABLE,
            )

        add("runtime.gio", "Runtime PyGObject/Gio", check_runtime)

        if system_info is None:
            record(
                _CheckOutcome(
                    self._result(
                        "hardware.adapter",
                        system_labels["hardware.adapter"],
                        CheckSeverity.ERROR,
                        "no se pudo detectar",
                        evidence=EvidenceKind.NOT_AVAILABLE,
                    ),
                    evaluated=False,
                )
            )
        else:
            add(
                "hardware.adapter",
                system_labels["hardware.adapter"],
                lambda: self._check_adapter(system_info),
            )

        devices_attempted = False
        devices: list[DeviceInfo] = []
        devices_error: Exception | None = None

        def load_devices() -> list[DeviceInfo]:
            nonlocal devices_attempted, devices_error, devices
            if not devices_attempted:
                devices_attempted = True
                try:
                    devices = self._bluetooth.list_devices()
                except Exception as error:
                    devices_error = error
            if devices_error is not None:
                raise devices_error
            return devices

        def check_paired() -> CheckResult | _CheckOutcome:
            try:
                current = load_devices()
            except BluetoothError:
                return _CheckOutcome(
                    self._result(
                        "device.paired",
                        "Dispositivos emparejados",
                        CheckSeverity.WARNING,
                        "BlueZ no responde",
                        evidence=EvidenceKind.NOT_AVAILABLE,
                    ),
                    evaluated=False,
                )
            paired = [device for device in current if device.paired]
            if paired:
                return self._result(
                    "device.paired",
                    "Dispositivos emparejados",
                    CheckSeverity.OK,
                    f"{len(paired)} emparejados",
                )
            return self._result(
                "device.paired",
                "Dispositivos emparejados",
                CheckSeverity.INFO,
                "sin dispositivos emparejados",
                evidence=EvidenceKind.NOT_AVAILABLE,
            )

        add("device.paired", "Dispositivos emparejados", check_paired)

        connected_device: DeviceInfo | None = None

        def check_connected() -> CheckResult | _CheckOutcome:
            nonlocal connected_device
            try:
                current = load_devices()
            except BluetoothError:
                return _CheckOutcome(
                    self._result(
                        "device.connected",
                        "Dispositivo conectado",
                        CheckSeverity.WARNING,
                        "BlueZ no responde",
                        evidence=EvidenceKind.NOT_AVAILABLE,
                    ),
                    evaluated=False,
                )
            connected_device = next((device for device in current if device.connected), None)
            if connected_device is None:
                return self._result(
                    "device.connected",
                    "Dispositivo conectado",
                    CheckSeverity.INFO,
                    "ninguno conectado",
                    evidence=EvidenceKind.NOT_AVAILABLE,
                )
            return self._result(
                "device.connected",
                "Dispositivo conectado",
                CheckSeverity.OK,
                "conectado",
            )

        add("device.connected", "Dispositivo conectado", check_connected)

        def no_connected(
            check_id: str,
            label: str,
            message: str,
        ) -> CheckResult | _CheckOutcome:
            outcome = self._result(
                check_id,
                label,
                CheckSeverity.INFO,
                message,
                evidence=EvidenceKind.NOT_AVAILABLE,
            )
            return _CheckOutcome(outcome, evaluated=devices_error is None)

        codec_attempted = False
        active_codec: CodecInfo | None = None
        codec_error: Exception | None = None

        def load_codec() -> CodecInfo | None:
            nonlocal codec_attempted, active_codec, codec_error
            if not codec_attempted:
                codec_attempted = True
                if connected_device is not None:
                    try:
                        active_codec = self._audio.get_active_codec(connected_device.address)
                    except Exception as error:
                        codec_error = error
            if codec_error is not None:
                raise codec_error
            return active_codec

        def check_profile() -> CheckResult | _CheckOutcome:
            if connected_device is None:
                return no_connected(
                    "audio.profile", "Perfil de audio activo", "perfil no disponible"
                )
            codec = load_codec()
            if codec is None:
                return self._result(
                    "audio.profile",
                    "Perfil de audio activo",
                    CheckSeverity.INFO,
                    "perfil no disponible",
                    evidence=EvidenceKind.NOT_AVAILABLE,
                )
            if codec.profile is BluetoothProfile.A2DP:
                return self._result(
                    "audio.profile",
                    "Perfil de audio activo",
                    CheckSeverity.OK,
                    "A2DP",
                )
            if codec.profile is BluetoothProfile.HFP:
                return self._result(
                    "audio.profile",
                    "Perfil de audio activo",
                    CheckSeverity.WARNING,
                    "HFP activo: calidad de reproducción degradada",
                )
            return self._result(
                "audio.profile",
                "Perfil de audio activo",
                CheckSeverity.INFO,
                "perfil no disponible",
                evidence=EvidenceKind.NOT_AVAILABLE,
            )

        add("audio.profile", "Perfil de audio activo", check_profile)

        def check_codec() -> CheckResult | _CheckOutcome:
            if connected_device is None:
                return no_connected("audio.codec", "Códec activo", "códec no disponible")
            codec = load_codec()
            if codec is None:
                return self._result(
                    "audio.codec",
                    "Códec activo",
                    CheckSeverity.INFO,
                    "códec no disponible",
                    evidence=EvidenceKind.NOT_AVAILABLE,
                )
            if codec.codec is CodecType.UNKNOWN:
                return self._result(
                    "audio.codec",
                    "Códec activo",
                    CheckSeverity.WARNING,
                    "códec no reconocido",
                    detail=codec.codec.value,
                )
            return self._result(
                "audio.codec",
                "Códec activo",
                CheckSeverity.OK,
                codec.codec.value,
                detail=codec.codec.value,
            )

        add("audio.codec", "Códec activo", check_codec)

        sink_missing = False

        def check_sink() -> CheckResult | _CheckOutcome:
            nonlocal sink_missing
            try:
                sink = self._audio.get_default_audio_sink()
            except WirePlumberUnavailableError:
                sink_missing = True
                return _CheckOutcome(
                    self._result(
                        "audio.sink_default",
                        "Sink por defecto del sistema",
                        CheckSeverity.INFO,
                        "sin sink por defecto",
                        evidence=EvidenceKind.NOT_AVAILABLE,
                    ),
                    evaluated=False,
                )
            if not sink:
                sink_missing = True
                return self._result(
                    "audio.sink_default",
                    "Sink por defecto del sistema",
                    CheckSeverity.INFO,
                    "sin sink por defecto",
                    evidence=EvidenceKind.NOT_AVAILABLE,
                )
            return self._result(
                "audio.sink_default",
                "Sink por defecto del sistema",
                CheckSeverity.OK,
                "sink por defecto disponible",
                detail=_sanitize(sink),
            )

        add("audio.sink_default", "Sink por defecto del sistema", check_sink)

        mic_active = False

        def check_mic() -> CheckResult | _CheckOutcome:
            nonlocal mic_active
            if connected_device is None:
                return no_connected("audio.mic", "Micrófono Bluetooth", "micrófono no disponible")
            nodes = self._audio.list_device_audio_nodes(connected_device.address)
            mic_active = any(node.media_class == "Audio/Source" for node in nodes)
            if mic_active:
                return self._result(
                    "audio.mic",
                    "Micrófono Bluetooth",
                    CheckSeverity.WARNING,
                    "micrófono HFP activo",
                )
            return self._result(
                "audio.mic",
                "Micrófono Bluetooth",
                CheckSeverity.OK,
                "sin micrófono activo",
            )

        add("audio.mic", "Micrófono Bluetooth", check_mic)

        def check_battery() -> CheckResult | _CheckOutcome:
            if connected_device is None:
                return no_connected(
                    "battery.aggregate", "Batería (agregada)", "batería no disponible"
                )
            battery = self._bluetooth.get_battery(connected_device.object_path)
            if battery is None or battery.percentage is None:
                return self._result(
                    "battery.aggregate",
                    "Batería (agregada)",
                    CheckSeverity.INFO,
                    "batería no disponible",
                    evidence=EvidenceKind.NOT_AVAILABLE,
                )
            percentage = f"{battery.percentage}%"
            return self._result(
                "battery.aggregate",
                "Batería (agregada)",
                CheckSeverity.INFO,
                percentage,
                detail=percentage,
            )

        add("battery.aggregate", "Batería (agregada)", check_battery)

        if (
            active_codec is not None and active_codec.profile is BluetoothProfile.HFP
        ) or mic_active:
            recommendations.append(
                "Activa Música (A2DP) con openbuds music para mejor calidad de reproducción"
            )
        if not runtime_ready:
            recommendations.append(
                "Ejecuta make check-runtime y recrea el venv con /usr/bin/python3 "
                "--system-site-packages"
            )
        if system_info is not None and not system_info.has_bluetooth_adapter:
            recommendations.append(
                "Verifica que el Bluetooth no esté bloqueado (rfkill) y que el adaptador exista"
            )
        if sink_missing:
            recommendations.append(
                "Inicia PipeWire/WirePlumber (systemctl --user) si el audio no funciona"
            )

        if not evaluated_any:
            overall_status = HealthStatus.UNKNOWN
        elif any(check.severity is CheckSeverity.ERROR for check in checks):
            overall_status = HealthStatus.ERROR
        elif any(check.severity is CheckSeverity.WARNING for check in checks):
            overall_status = HealthStatus.WARNING
        else:
            overall_status = HealthStatus.OK

        return HealthReport(
            overall_status=overall_status,
            checks=tuple(checks),
            recommendations=tuple(dict.fromkeys(recommendations)),
            generated_at=datetime.now(UTC).isoformat(),
        )

    def run_benchmark(self, device_address: str, duration_seconds: int = 10) -> BenchmarkResult:
        """Benchmark support is intentionally deferred to a later stage."""
        raise NotImplementedError

    @staticmethod
    def _run_isolated(
        check_id: str,
        label: str,
        callback: Callable[[], CheckResult | _CheckOutcome],
    ) -> _CheckOutcome:
        try:
            outcome = callback()
        except Exception:
            return _CheckOutcome(
                HealthCheckRepository._result(
                    check_id,
                    label,
                    CheckSeverity.ERROR,
                    "no se pudo evaluar",
                    evidence=EvidenceKind.NOT_AVAILABLE,
                ),
                evaluated=False,
            )
        if isinstance(outcome, _CheckOutcome):
            return outcome
        return _CheckOutcome(outcome)

    @staticmethod
    def _result(
        check_id: str,
        label: str,
        severity: CheckSeverity,
        message: str,
        *,
        detail: str = "",
        evidence: EvidenceKind = EvidenceKind.OBSERVED,
    ) -> CheckResult:
        return CheckResult(
            check_id=check_id,
            label=label,
            severity=severity,
            message=message,
            detail=detail,
            evidence=evidence,
        )

    @classmethod
    def _check_os(cls, info: SystemInfo) -> CheckResult:
        if info.is_supported:
            return cls._result(
                "system.os",
                "Sistema operativo",
                CheckSeverity.OK,
                f"Ubuntu {info.os_version} soportado",
            )
        return cls._result(
            "system.os",
            "Sistema operativo",
            CheckSeverity.ERROR,
            "sistema no soportado",
        )

    @classmethod
    def _check_version(
        cls,
        check_id: str,
        label: str,
        component: str,
        version: str,
    ) -> CheckResult:
        if version:
            return cls._result(
                check_id,
                label,
                CheckSeverity.OK,
                f"{component} disponible",
                detail=version,
            )
        return cls._result(
            check_id,
            label,
            CheckSeverity.ERROR,
            f"{component} no disponible",
            evidence=EvidenceKind.NOT_AVAILABLE,
        )

    @classmethod
    def _check_wireplumber(cls, info: SystemInfo) -> CheckResult:
        if not info.wireplumber_version or not info.wireplumber_config_style:
            return cls._result(
                "system.wireplumber",
                "WirePlumber",
                CheckSeverity.ERROR,
                "WirePlumber no disponible",
                evidence=EvidenceKind.NOT_AVAILABLE,
            )
        detail = f"{info.wireplumber_version} ({info.wireplumber_config_style})"
        if info.wireplumber_config_style == "lua-0.4":
            return cls._result(
                "system.wireplumber",
                "WirePlumber",
                CheckSeverity.OK,
                "WirePlumber disponible",
                detail=detail,
            )
        return cls._result(
            "system.wireplumber",
            "WirePlumber",
            CheckSeverity.WARNING,
            "estilo de configuración no estándar (se espera lua-0.4)",
            detail=detail,
        )

    @classmethod
    def _check_system_bus(cls, info: SystemInfo) -> CheckResult:
        if info.system_bus_available:
            return cls._result(
                "system.dbus",
                "Bus del sistema",
                CheckSeverity.OK,
                "bus del sistema disponible",
            )
        return cls._result(
            "system.dbus",
            "Bus del sistema",
            CheckSeverity.ERROR,
            "bus del sistema no disponible",
            evidence=EvidenceKind.NOT_AVAILABLE,
        )

    @classmethod
    def _check_adapter(cls, info: SystemInfo) -> CheckResult:
        if info.has_bluetooth_adapter:
            return cls._result(
                "hardware.adapter",
                "Adaptador Bluetooth",
                CheckSeverity.OK,
                "adaptador detectado",
            )
        return cls._result(
            "hardware.adapter",
            "Adaptador Bluetooth",
            CheckSeverity.WARNING,
            "no se detectó adaptador (verifica rfkill o hardware); la ausencia no "
            "invalida el resto",
            evidence=EvidenceKind.NOT_AVAILABLE,
        )


def _sanitize(value: str) -> str:
    """Redact Bluetooth addresses and BlueZ object paths in sink details."""
    sanitized = _REDACT_OBJECT_PATH.sub("<redacted>", value)
    sanitized = _REDACT_ADDRESS.sub("<redacted>", sanitized)
    return "".join(character if character.isprintable() else "?" for character in sanitized)[:80]
