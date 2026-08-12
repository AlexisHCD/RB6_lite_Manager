"""Single-window Qt MVP for OpenBuds Manager."""

from __future__ import annotations

import ctypes.util
import os
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from openbuds.core.errors import OpenBudsError

if TYPE_CHECKING:
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QMainWindow

    from openbuds.presentation.qt.view_models.device_view_model import DeviceViewModel

_QT_IMPORT_ERROR: ImportError | None = None
try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import (
        QApplication,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:  # pragma: no cover - exercised only without the optional GUI runtime
    _QT_IMPORT_ERROR = exc
else:
    from openbuds.presentation.qt.view_models.device_view_model import DeviceViewModel

_FIELD_NAMES = (
    "Dispositivo",
    "Estado",
    "Batería",
    "RSSI",
    "Perfil",
    "Códec",
    "Sink",
    "Source",
)
_MIC_WARNING = "Activar el micrófono Bluetooth (HFP) puede reducir la calidad de reproducción."


def _require_qt() -> None:
    """Raise a clear application error when the Qt runtime is unavailable."""
    if _QT_IMPORT_ERROR is not None:
        raise OpenBudsError("la interfaz gráfica requiere PySide6 instalado") from _QT_IMPORT_ERROR


def _display_is_available() -> bool:
    """Return whether Qt can use a display or an explicitly selected test backend."""
    platform = os.environ.get("QT_QPA_PLATFORM", "").casefold()
    if platform in {"offscreen", "minimal", "vnc"}:
        return True
    if os.environ.get("WAYLAND_DISPLAY"):
        return True
    if os.environ.get("DISPLAY"):
        return ctypes.util.find_library("xcb-cursor") is not None
    return False


def build_default_view_model() -> DeviceViewModel:
    """Compose the real read-only and approved session use cases for the GUI."""
    _require_qt()
    from openbuds.application.get_device_info import GetDeviceInfoUseCase
    from openbuds.application.scan_devices import ScanDevicesUseCase
    from openbuds.application.session_control import (
        ConnectDeviceUseCase,
        DisconnectDeviceUseCase,
        SetAudioProfileUseCase,
    )
    from openbuds.infrastructure.bluez.bluez_repository import BlueZRepository
    from openbuds.infrastructure.pipewire.pipewire_control_repository import (
        PipeWireControlRepository,
    )
    from openbuds.infrastructure.pipewire.pipewire_repository import PipeWireRepository

    bluetooth = BlueZRepository()
    return DeviceViewModel(
        scan=ScanDevicesUseCase(bluetooth),
        info=GetDeviceInfoUseCase(bluetooth, PipeWireRepository()),
        connect_uc=ConnectDeviceUseCase(bluetooth),
        disconnect_uc=DisconnectDeviceUseCase(bluetooth),
        profile_uc=SetAudioProfileUseCase(PipeWireControlRepository()),
    )


if _QT_IMPORT_ERROR is None:

    class MainWindow(QMainWindow):
        """Display one selected Bluetooth device and its available controls."""

        def __init__(self, view_model: DeviceViewModel | None = None) -> None:
            super().__init__()
            self.setWindowTitle("OpenBuds Manager")
            self.setMinimumSize(480, 360)
            self.view_model = view_model if view_model is not None else build_default_view_model()
            self._value_labels: dict[str, QLabel] = {}
            self._build_ui()

            self.view_model.state_changed.connect(self._render_state)
            self.view_model.warning.connect(self._show_warning)
            self._refresh_timer = QTimer(self)
            self._refresh_timer.setInterval(2000)
            self._refresh_timer.timeout.connect(self.view_model.refresh)
            self._render_state()
            self._refresh_timer.start()
            self.view_model.refresh()

        def _build_ui(self) -> None:
            central = QWidget(self)
            self.setCentralWidget(central)
            root_layout = QVBoxLayout(central)

            state_group = QGroupBox("Estado del dispositivo", central)
            state_layout = QFormLayout(state_group)
            for field_name in _FIELD_NAMES:
                value_label = QLabel("No disponible", state_group)
                value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                value_label.setAccessibleName(f"Valor de {field_name}")
                self._value_labels[field_name] = value_label
                state_layout.addRow(QLabel(f"{field_name}:", state_group), value_label)
            root_layout.addWidget(state_group)

            actions_layout = QHBoxLayout()
            self.connect_button = self._button("Conectar", self._on_connect)
            self.disconnect_button = self._button("Desconectar", self._on_disconnect)
            self.music_button = self._button("Música", self._on_music)
            self.mic_button = self._button("Micrófono", self._on_mic)
            self.refresh_button = self._button("Actualizar", self.view_model.refresh)
            for button in (
                self.connect_button,
                self.disconnect_button,
                self.music_button,
                self.mic_button,
                self.refresh_button,
            ):
                actions_layout.addWidget(button)
            root_layout.addLayout(actions_layout)

            diagnostic_layout = QHBoxLayout()
            diagnostic_layout.addStretch()
            self.diagnostic_button = self._button("Diagnóstico", self._on_diagnostic)
            diagnostic_layout.addWidget(self.diagnostic_button)
            root_layout.addLayout(diagnostic_layout)

            self.status_label = QLabel("Listo", central)
            self.status_label.setAccessibleName("Estado de la aplicación")
            self.statusBar().addWidget(self.status_label)

        @staticmethod
        def _button(text: str, handler: Callable[[], None]) -> QPushButton:
            button = QPushButton(text)
            button.setAccessibleName(text)
            button.clicked.connect(handler)
            return button

        def _text_value(self, attribute: str) -> str:
            return cast(str, getattr(self.view_model, attribute))

        def _busy_value(self) -> bool:
            return cast(bool, self.view_model.busy)

        def _render_state(self) -> None:
            values = {
                "Dispositivo": self._text_value("device_name"),
                "Estado": self._text_value("connection"),
                "Batería": self._text_value("battery"),
                "RSSI": self._text_value("rssi"),
                "Perfil": self._text_value("profile"),
                "Códec": self._text_value("codec"),
                "Sink": self._text_value("sink"),
                "Source": self._text_value("source"),
            }
            for field_name, value in values.items():
                self._value_labels[field_name].setText(value)

            error = self._text_value("error")
            if error:
                self.status_label.setText(f"Error: {error}")
            elif self._busy_value():
                self.status_label.setText("Actualizando...")
            else:
                self.status_label.setText("Listo")
            self._update_controls()

        def _update_controls(self) -> None:
            available = not self._busy_value()
            connection = self._text_value("connection")
            self.connect_button.setEnabled(available and connection == "emparejado")
            self.disconnect_button.setEnabled(available and connection == "conectado")
            connected = available and connection == "conectado"
            self.music_button.setEnabled(connected)
            self.mic_button.setEnabled(connected)
            self.refresh_button.setEnabled(available)
            self.diagnostic_button.setEnabled(available)

        def _confirm(self, title: str, message: str) -> bool:
            answer = QMessageBox.question(
                self,
                title,
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            return answer == QMessageBox.StandardButton.Yes

        def _on_connect(self) -> None:
            name = self.view_model.device_name
            if self._confirm("Conectar dispositivo", f"¿Conectar {name}?"):
                self.view_model.connect_device()

        def _on_disconnect(self) -> None:
            name = self.view_model.device_name
            if self._confirm("Desconectar dispositivo", f"¿Desconectar {name}?"):
                self.view_model.disconnect_device()

        def _on_music(self) -> None:
            name = self.view_model.device_name
            if self._confirm("Activar música", f"¿Activar Música (A2DP) en {name}?"):
                self.view_model.music()

        def _on_mic(self) -> None:
            prepare_warning = getattr(self.view_model, "prepare_mic_warning", None)
            if callable(prepare_warning):
                prepare_warning()
            else:
                self._show_warning(_MIC_WARNING)
            name = self.view_model.device_name
            if self._confirm("Activar micrófono", f"¿Activar Micrófono (HFP) en {name}?"):
                self.view_model.mic()
            else:
                cancel_warning = getattr(self.view_model, "cancel_mic_warning", None)
                if callable(cancel_warning):
                    cancel_warning()

        def _on_diagnostic(self) -> None:
            QMessageBox.information(
                self,
                "Diagnóstico",
                "Ejecuta openbuds doctor en la terminal",
            )

        def _show_warning(self, message: str) -> None:
            QMessageBox.warning(self, "Advertencia", message)

        def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
            """Stop the refresh loop and background worker before closing."""
            self._refresh_timer.stop()
            self.view_model.close()
            super().closeEvent(event)

else:

    class MainWindow:  # type: ignore[no-redef]
        """Fallback that reports the missing optional Qt runtime clearly."""

        def __init__(self, view_model: DeviceViewModel | None = None) -> None:
            del view_model
            _require_qt()


def build_main_window(view_model: DeviceViewModel | None = None) -> QMainWindow:
    """Build the single main window with an injected or real ViewModel."""
    _require_qt()
    return MainWindow(view_model if view_model is not None else build_default_view_model())


def run_app() -> int:
    """Run the Qt application; fail clearly when no graphical display exists."""
    _require_qt()
    if QApplication.instance() is None and not _display_is_available():
        raise OpenBudsError("la interfaz gráfica requiere un display utilizable")
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    window = build_main_window()
    window.show()
    return app.exec()


__all__ = ["MainWindow", "build_default_view_model", "build_main_window", "run_app"]
