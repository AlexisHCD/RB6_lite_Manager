"""Qt ViewModel and worker for the single-device MVP screen."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import Literal

from PySide6.QtCore import Property, QObject, Qt, QThread, Signal, Slot

from openbuds.application.get_device_info import DeviceAggregate, GetDeviceInfoUseCase
from openbuds.application.scan_devices import ScanDevicesRequest, ScanDevicesUseCase
from openbuds.application.session_control import (
    ConnectDeviceRequest,
    ConnectDeviceUseCase,
    DisconnectDeviceRequest,
    DisconnectDeviceUseCase,
    SetAudioProfileRequest,
    SetAudioProfileUseCase,
)
from openbuds.core.errors import OpenBudsError
from openbuds.domain.enums import BluetoothProfile
from openbuds.domain.models import DeviceInfo
from openbuds.presentation.formatting import aggregate_fields, sanitize_display_field

_NO_DEVICES = "Sin dispositivos emparejados"
_NO_DATA = "No disponible"
_MIC_WARNING = "Activar el micrófono Bluetooth (HFP) puede reducir la calidad de reproducción."
_Action = Literal["connect", "disconnect", "music", "mic"]
_Operation = Literal["refresh", "connect", "disconnect", "music", "mic"]


def _empty_fields() -> dict[str, str]:
    """Return the stable empty-state values used by the UI."""
    return {
        "Dispositivo": _NO_DEVICES,
        "Estado": _NO_DATA,
        "Batería": _NO_DATA,
        "RSSI": _NO_DATA,
        "Perfil": _NO_DATA,
        "Códec": _NO_DATA,
        "Sink": _NO_DATA,
        "Source": _NO_DATA,
    }


def _safe_error(message: str) -> str:
    """Remove addresses and BlueZ object paths from a user-facing error."""
    safe_message = sanitize_display_field(message)
    return safe_message or "No se pudo completar la operación."


@dataclass(frozen=True, slots=True)
class _RefreshResult:
    """Result of selecting a paired device and collecting its aggregate."""

    selected: DeviceInfo | None
    aggregate: DeviceAggregate | None


class DeviceWorker(QObject):
    """Run presentation tasks serially on a dedicated Qt thread."""

    finished = Signal(object)
    failed = Signal(str)
    _task_ready = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._tasks: deque[Callable[[], object]] = deque()
        self._lock = Lock()
        self._closed = False
        self._thread = QThread()
        self._task_ready.connect(self._process_next, Qt.ConnectionType.QueuedConnection)
        self.moveToThread(self._thread)
        self._thread.start()

    def run(self, task: Callable[[], object]) -> None:
        """Queue one callable for execution on the worker thread."""
        with self._lock:
            if self._closed:
                raise RuntimeError("device worker is closed")
            self._tasks.append(task)
        self._task_ready.emit()

    @Slot()
    def _process_next(self) -> None:
        with self._lock:
            if not self._tasks or self._closed:
                return
            task = self._tasks.popleft()

        try:
            result = task()
        except OpenBudsError as exc:
            self.failed.emit(_safe_error(str(exc)))
        except Exception as exc:
            self.failed.emit(_safe_error(str(exc)))
        else:
            self.finished.emit(result)

        with self._lock:
            has_next = bool(self._tasks) and not self._closed
        if has_next:
            self._task_ready.emit()

    def close(self) -> None:
        """Stop the worker after its current task has returned."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._tasks.clear()
        self._thread.quit()
        if self._thread != QThread.currentThread():
            self._thread.wait()


class DeviceViewModel(QObject):
    """Expose aggregate state and session commands to Qt widgets."""

    state_changed = Signal()
    warning = Signal(str)

    def __init__(
        self,
        scan: ScanDevicesUseCase,
        info: GetDeviceInfoUseCase,
        connect_uc: ConnectDeviceUseCase,
        disconnect_uc: DisconnectDeviceUseCase,
        profile_uc: SetAudioProfileUseCase,
    ) -> None:
        super().__init__()
        self._scan = scan
        self._info = info
        self._connect_uc = connect_uc
        self._disconnect_uc = disconnect_uc
        self._profile_uc = profile_uc
        self._worker = DeviceWorker()
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.failed.connect(self._on_worker_failed)
        self._fields = _empty_fields()
        self._device_path: str | None = None
        self._device_address: str | None = None
        self._busy = False
        self._error = ""
        self._operation: _Operation | None = None
        self._mic_warning_pending = False

    @Property(str, notify=state_changed)
    def device_name(self) -> str:
        """Return the current display name."""
        return self._fields["Dispositivo"]

    @Property(str, notify=state_changed)
    def connection(self) -> str:
        """Return the current connection label."""
        return self._fields["Estado"]

    @Property(str, notify=state_changed)
    def battery(self) -> str:
        """Return the aggregate battery label."""
        return self._fields["Batería"]

    @Property(str, notify=state_changed)
    def rssi(self) -> str:
        """Return the aggregate RSSI label."""
        return self._fields["RSSI"]

    @Property(str, notify=state_changed)
    def profile(self) -> str:
        """Return the verified Bluetooth profile label."""
        return self._fields["Perfil"]

    @Property(str, notify=state_changed)
    def codec(self) -> str:
        """Return the verified codec label."""
        return self._fields["Códec"]

    @Property(str, notify=state_changed)
    def sink(self) -> str:
        """Return the first observed Bluetooth sink label."""
        return self._fields["Sink"]

    @Property(str, notify=state_changed)
    def source(self) -> str:
        """Return the first observed Bluetooth source label."""
        return self._fields["Source"]

    @Property(bool, notify=state_changed)
    def busy(self) -> bool:
        """Return whether a read or session operation is in progress."""
        return self._busy

    @Property(str, notify=state_changed)
    def error(self) -> str:
        """Return the current safe error message, if any."""
        return self._error

    @Slot()
    def refresh(self) -> None:
        """Refresh the selected paired device without blocking the UI."""
        if self._busy:
            return
        self._begin_task("refresh", self._refresh_task)

    @Slot()
    def connect_device(self) -> None:
        """Connect the selected paired device."""
        if self._busy:
            return
        device_path = self._device_path
        if device_path is None:
            self._set_error("No hay un dispositivo emparejado seleccionado.")
            return
        self._begin_action(
            "connect", lambda: self._connect_uc.execute(ConnectDeviceRequest(device_path))
        )

    @Slot()
    def disconnect_device(self) -> None:
        """Disconnect the selected device."""
        if self._busy:
            return
        device_path = self._device_path
        if device_path is None:
            self._set_error("No hay un dispositivo seleccionado.")
            return
        self._begin_action(
            "disconnect", lambda: self._disconnect_uc.execute(DisconnectDeviceRequest(device_path))
        )

    @Slot()
    def music(self) -> None:
        """Select the runtime A2DP profile for the selected device."""
        if self._busy:
            return
        device_address = self._device_address
        if device_address is None:
            self._set_error("No hay un dispositivo conectado seleccionado.")
            return
        self._begin_action(
            "music",
            lambda: self._profile_uc.execute(
                SetAudioProfileRequest(device_address, BluetoothProfile.A2DP)
            ),
        )

    @Slot()
    def mic(self) -> None:
        """Warn about quality degradation and select the runtime HFP profile."""
        if self._busy:
            return
        if not self._mic_warning_pending:
            self.warning.emit(_MIC_WARNING)
        self._mic_warning_pending = False
        device_address = self._device_address
        if device_address is None:
            self._set_error("No hay un dispositivo conectado seleccionado.")
            return
        self._begin_action(
            "mic",
            lambda: self._profile_uc.execute(
                SetAudioProfileRequest(device_address, BluetoothProfile.HFP)
            ),
        )

    @Slot()
    def prepare_mic_warning(self) -> None:
        """Emit the microphone warning before the UI asks for confirmation."""
        if not self._busy:
            self._mic_warning_pending = True
            self.warning.emit(_MIC_WARNING)

    @Slot()
    def cancel_mic_warning(self) -> None:
        """Clear a microphone warning that was not confirmed."""
        self._mic_warning_pending = False

    @Slot()
    def close(self) -> None:
        """Close the background worker."""
        self._worker.close()

    def _refresh_task(self) -> _RefreshResult:
        devices = self._scan.execute(ScanDevicesRequest(include_paired_only=True))
        selected = next((device for device in devices if device.connected), None)
        if selected is None and devices:
            selected = devices[0]
        if selected is None:
            return _RefreshResult(None, None)
        return _RefreshResult(selected, self._info.execute(selected.object_path))

    def _begin_action(self, action: _Action, task: Callable[[], object]) -> None:
        if self._busy:
            return
        self._begin_task(action, task)

    def _begin_task(self, operation: _Operation, task: Callable[[], object]) -> None:
        self._operation = operation
        self._error = ""
        self._busy = True
        self.state_changed.emit()
        try:
            self._worker.run(task)
        except Exception as exc:
            self._on_worker_failed(_safe_error(str(exc)))

    def _queue_refresh_after_action(self) -> None:
        self._operation = "refresh"
        try:
            self._worker.run(self._refresh_task)
        except Exception as exc:
            self._on_worker_failed(_safe_error(str(exc)))

    @Slot(object)
    def _on_worker_finished(self, result: object) -> None:
        operation = self._operation
        if operation is None:
            return
        if operation == "refresh":
            if not isinstance(result, _RefreshResult):
                self._on_worker_failed("No se pudo interpretar el estado del dispositivo.")
                return
            self._apply_refresh(result)
            self._operation = None
            self._busy = False
            self.state_changed.emit()
            return
        self._queue_refresh_after_action()

    @Slot(str)
    def _on_worker_failed(self, message: str) -> None:
        self._operation = None
        self._error = _safe_error(message)
        self._busy = False
        self.state_changed.emit()

    def _apply_refresh(self, result: _RefreshResult) -> None:
        aggregate = result.aggregate
        if result.selected is None or aggregate is None:
            self._fields = _empty_fields()
            self._device_path = None
            self._device_address = None
            return
        self._fields = aggregate_fields(aggregate)
        self._device_path = aggregate.device.object_path
        self._device_address = aggregate.device.address

    def _set_error(self, message: str) -> None:
        self._error = _safe_error(message)
        self.state_changed.emit()


__all__ = ["DeviceViewModel", "DeviceWorker"]
